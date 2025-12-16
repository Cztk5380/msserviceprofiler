# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

from enum import Enum, auto
from collections import deque
from multiprocessing import Queue, Process
from multiprocessing import Pool
from ms_service_profiler.task.task_register import filter_dag
from ms_service_profiler.task.task_register import TaskDag
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger, Color
from ms_service_profiler.utils.error import OtherTaskError


class DefaultValue(Enum):
    UNFILLED = auto()


class SubprocessInfo:
    def __init__(self) -> None:
        self.executor = None
        self.queues = []
        self.processes = []
    
    def get_queues(self):
        return self.queues
    
    def add_queue(self, queue):
        self.queues.append(queue)
    
    def new_process(self, send_queue, args):
        recv_queue = Queue()
        args = args + (recv_queue, send_queue)
        process = Process(target=task_run, args=args)
        self.queues.append(recv_queue)
        self.processes.append(process)
        process.start()
        
    def is_alive(self):
        return any((x.is_alive for x in self.processes))


class TaskManager:
    def __init__(self, task_dag: TaskDag) -> None:
        self.task_dag = task_dag
        self.task_manager_info_dict = dict()
        self.manager_recv_queue = Queue()
        self.pool = []
        self.pool_owner = []
        
    def init_task(self, task_name) -> None:
        self.task_manager_info_dict.setdefault(task_name, dict(process_pool_info=[],
                                                               wait_pool_index=[],
                                                               queues=[],
                                                               state="unstart",
                                                               gather_data=deque()))
        return self.task_manager_info_dict[task_name]

    def init_task_waiting_pool(self, src_dag, pool_index):
        for task_name, _ in src_dag.get_ordered_task_names():
            task_manager_info = self.init_task(task_name)
            task_manager_info.get("wait_pool_index").append(pool_index)
    
    def create_pool(self, data_source_task, single_data_list, src_dag, args):
        task_manager_info = self.init_task(data_source_task.name)
        process_info = SubprocessInfo()
        pool_index = len(self.pool)
        self.pool.append(process_info)
        self.pool_owner.append(data_source_task.name)
        task_manager_info.get("process_pool_info").append(process_info)
        queues = process_info.get_queues()
        self.init_task_waiting_pool(src_dag, pool_index)
        # 启动进程
        for _, data in enumerate(single_data_list):
            process_info.new_process(self.manager_recv_queue, (data, src_dag, pool_index, args))

        task_manager_info.get("queues").extend(queues)

        self.send_go(data_source_task.name)
    
    def set_no_source_data(self, task_name):
        task_manager_info = self.init_task(task_name)
        task_manager_info["state"] = "no_source_data"
        # 如果它的 next-task 的所有 prev-tasks 都是没数据，那 next-task 也置为没数据
        for next_task_name in self.task_dag.get_next_task_names(task_name):
            no_source_flag = True
            for prev_task_name in self.task_dag.get_prev_task_names(next_task_name):
                prev_task_manager_info = self.init_task(prev_task_name)
                if prev_task_manager_info.get("state") != "no_source_data":
                    no_source_flag = False
                    break

            if no_source_flag:
                self.set_no_source_data(next_task_name)

    def get_task_state(self, task_name):
        task_manager_info = self.init_task(task_name)
        return task_manager_info.get("state", "unstart")
    
    def get_task_process_cnt(self, task_name):
        task_manager_info = self.init_task(task_name)
        return len(task_manager_info.get("queues", []))
    
    def is_all_finished(self):
        return all((x is None for x in self.pool_owner)) or all((not x.is_alive() for x in self.pool))
    
    def is_all_prev_finished(self, task_name):
        # 前置task 全部完成
        error_flag = False
        for prev_task_name in self.task_dag.get_prev_task_names(task_name):
            if self.get_task_state(prev_task_name) == "error":
                error_flag = True
            if self.get_task_state(prev_task_name) not in ["finished", "no_source_data", "error"]:
                return False, error_flag
            
        # 且pool 都释放给当前task 啦~
        task_manager_info = self.init_task(task_name)
        for wait_pool_index in task_manager_info.get("wait_pool_index"):
            if self.pool_owner[wait_pool_index] != task_name:
                return False, error_flag
            
        return True, error_flag

    def set_task_finished(self, finished_task_name, next_task_set):
        task_manager_info = self.init_task(finished_task_name)
        if task_manager_info["state"] != 'error':
            task_manager_info["state"] = "finished"
            logger.info(f"{Color.BRIGHT_GREEN}task [{finished_task_name}] finished.{Color.RESET}")
        # 将这个进程信息转移到下一个task中去
        for pool_index, next_task_name in next_task_set:
            self.pool_owner[pool_index] = next_task_name
            if next_task_name is None:
                continue
        
            next_task_manager_info = self.init_task(next_task_name)
            next_task_manager_info.get("process_pool_info", []).append(self.pool[pool_index])
            next_task_manager_info.get("queues", []).extend(self.pool[pool_index].get_queues())
        
            # 判断前置流程是否全部完成
            all_finished, has_err = self.is_all_prev_finished(next_task_name)
            if next_task_manager_info["state"] != "unstart":
                continue
            if all_finished:
                next_task_manager_info = self.init_task(next_task_name)
                next_task_manager_info["state"] = "started"
                if has_err:
                    self.send_go(next_task_name, "error")
                else:
                    self.send_go(next_task_name)
            else:
                pass


    def set_task_error(self, error_task_name, error_index, err_msg):
        # 如果状态不是 error，清空 gather 数据，填 error。 在 error 状态之后，后面所有 gather 数据均不接收
        task_manager_info = self.init_task(error_task_name)
        if task_manager_info.get("state") != "error":
            task_manager_info.get("gather_data").clear()
        if err_msg:
            logger.error(f"{Color.BRIGHT_RED}task [{error_task_name}] error. due to {err_msg} {Color.RESET}")

        task_manager_info["state"] = "error"
        return self.fill_gater_data(error_task_name, error_index, err_msg, ignore_error_state=True)

    def send_msg_to_one_process(self, task_name, task_index, msg, param):
        task_manager_info = self.init_task(task_name)
        if task_index < len(task_manager_info.get("queues", [])): # 求检视
            task_manager_info.get("queues", [])[task_index].put((msg, param))
    
    def send_msg_to_one_task(self, task_name, msg, param):
        task_manager_info = self.init_task(task_name)

        for queue in task_manager_info.get("queues", []):
            queue.put((msg, param))

    def send_go(self, task_name, go_msg="go"):
        logger.info(f"{Color.BRIGHT_BLUE}task [{task_name}] start. {Color.RESET}")
        for index in range(self.get_task_process_cnt(task_name)):
            self.send_msg_to_one_process(task_name, index, go_msg, index)
    
    def fill_gater_data(self, task_name, task_index, data, ignore_error_state=False):
        task_manager_info = self.init_task(task_name)
        if task_manager_info.get('state') == 'error' and ignore_error_state is False:
            return None
        # 从前往后排查 task_index 是否有值，都没有就创建一个 list 插入 deque
        gather_data = task_manager_info.get("gather_data")
        for deque_index, list_item in enumerate(gather_data):
            if list_item[task_index] is not DefaultValue.UNFILLED:
                continue
            list_item[task_index] = data
            if deque_index == 0 and all((x is not DefaultValue.UNFILLED for x in list_item)):
                return gather_data.popleft()
            break
        else:
            cnt = len(task_manager_info.get("queues", []))
            if cnt == 1:
                return [data]

            list_item = [DefaultValue.UNFILLED] * cnt
            list_item[task_index] = data
            gather_data.append(list_item)
        
        return None

    def start(self):
        while (True):
            who_task_name, who_index, msg, param = self.manager_recv_queue.get()
            if msg == "finished":
                data, after_error = param
                gather_data = self.fill_gater_data(who_task_name, who_index, data, ignore_error_state=after_error)
                if gather_data is not None:
                    self.send_msg_to_one_task(who_task_name, msg, None)
                    self.set_task_finished(who_task_name, set(gather_data))
                
                if self.is_all_finished():
                    break
            elif msg == "error":
                err_msg = param
                if err_msg is not None:
                    self.send_msg_to_one_task(who_task_name, msg, f"task {who_index} occurs error. due to {err_msg}")
                gather_err = self.set_task_error(who_task_name, who_index, err_msg)
                if gather_err is not None:
                    self.send_msg_to_one_task(who_task_name, "error_gather", gather_err)
                if self.is_all_finished():
                    break
            elif msg == "crash":
                for task_name in self.task_manager_info_dict.keys():
                    self.send_msg_to_one_task(task_name, "error", None)
                break
            elif msg == "gather":
                dst, data = param
                gather_data = self.fill_gater_data(who_task_name, who_index, data)
                if gather_data is not None:
                    self.send_msg_to_one_process(who_task_name, dst, msg, gather_data)
            elif msg == "all_gather":
                data = param
                gather_data = self.fill_gater_data(who_task_name, who_index, data)
                if gather_data is not None:
                    self.send_msg_to_one_task(who_task_name, msg, gather_data)
            elif msg == "broadcast":
                data = param
                self.send_msg_to_one_task(who_task_name, msg, data)
            elif msg == "send_to":
                dst, data = param
                self.send_msg_to_one_process(who_task_name, dst, 'p2p', data)
            else:
                pass


# sub process
def task_run(input_data, src_dag, pool_index, args, recv_queue, send_queue):
    task_index = None
    run_res_data = dict(prof_path=input_data)
    
    def recv():
        msg, gather_data = recv_queue.get()
        if msg == 'error':
            raise OtherTaskError(gather_data)
        return msg, gather_data
            
    def recv_ignore_error():
        msg = "error"
        while msg == 'error':
            msg, gather_data = recv_queue.get()
            if msg != 'error':
                return msg, gather_data
        
    def finished_sync(task_name, task_index, next_task_name, after_error=False):
        send_queue.put((task_name, task_index, "finished", ((pool_index, next_task_name), after_error)))
        msg, _ = recv()
        if msg != 'finished':
            raise ValueError("Expected 'finished' message, but received: {}".format(msg))
        
    def error_sync(task_name, task_index, err_msg=None):
        # 发送 error 到主进程
        send_queue.put((task_name, task_index, "error", err_msg))
        # 等待主进程同步到所有的其他进程，所有进程一起继续执行
        msg, gather_data = recv_ignore_error()
        return msg, gather_data
        
    def crash(task_name, task_index):
        send_queue.put((task_name, task_index, "crash", None))
    
    for task_name, next_task_name in src_dag.get_ordered_task_names():
        try:
            _, task_index = recv()
        
            task_info = TaskDag.get_task_reg_info(task_name)
            if isinstance(task_info.task_cls, Task):
                task_ins = task_info.task_cls
            else:
                task_ins = task_info.task_cls(args)
            
            task_ins.init(task_name, task_index, recv, send_queue)
            
            for depends_name in TaskDag.get_depends_data_names(task_name):
                if depends_name in run_res_data:
                    task_ins.set_depends_result(depends_name, run_res_data.get(depends_name, None))
            task_res = task_ins.run()
            
            for output_name in TaskDag.get_outputs_data_names(task_name):
                run_res_data.setdefault(output_name, task_res)
            
            # 等所有进程全部结束
            finished_sync(task_name, task_index, next_task_name)
        except OtherTaskError as e:
            error_sync(task_name, task_index, None)
            finished_sync(task_name, task_index, next_task_name, after_error=True)
            if args.log_level == 'verbose':
                break
        except Exception as e:
            error_sync(task_name, task_index, str(e))
            finished_sync(task_name, task_index, next_task_name, after_error=True)
            logger.exception(f'{task_name}-{task_index} error. {str(e)}')
            if args.log_level == 'verbose':
                crash(task_name, task_index)
                raise


# main process
@timer()
def tasks_run(data_source_tasks, task_dag, input_path, args):
    task_manager = TaskManager(task_dag)
    
    has_tasks = False
    for data_source_task in data_source_tasks:
        single_data_list = data_source_task.task_cls.get_prof_paths(input_path)
        # 如果没有数据，直接返回
        if len(single_data_list) == 0:
            task_manager.set_no_source_data(data_source_task.name)
            continue
        has_tasks = True
        # 创建进程池
        src_dag = filter_dag(task_dag, data_source_task.name)
        
        task_manager.create_pool(data_source_task, single_data_list, src_dag, args)

    # 所有都开始
    if has_tasks:
        task_manager.start()
