# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from enum import Enum, auto
from collections import deque


class DefaultValue(Enum):
    UNDEFINED = auto()

regist_map = dict()


class TaskRegisterInfo:
    def __init__(self, name, task_cls, data_depends, data_outputs) -> None:
        self.name = name
        self.task_cls = task_cls
        self.data_depends = data_depends
        self.data_outputs = data_outputs
    
    def get(self, key, default_value):
        return getattr(self, key, default_value)


class TaskDag:
    def __init__(self, dag_data_flow, dag_task_flow, head_tasks_name, ordered_tasks_name):
        self.dag_data_flow = dag_data_flow
        self.dag_task_flow = dag_task_flow
        self.head_tasks_name = head_tasks_name
        self.ordered_tasks_name = ordered_tasks_name

    @staticmethod
    def get_depends_data_names(task_name):
        return get_register_by_name(task_name).data_depends
    
    @staticmethod
    def get_outputs_data_names(task_name):
        return get_register_by_name(task_name).data_outputs
    
    @staticmethod
    def get_task_reg_info(task_name):
        return get_register_by_name(task_name)
    
    def get_next_task_names(self, task_name):
        return self.dag_task_flow.get(task_name, {}).get("next_task_name", [])
    
    def get_prev_task_names(self, task_name):
        return self.dag_task_flow.get(task_name, {}).get("prev_task_name", [])

    def get_from_task_names(self, data_name):
        return self.dag_data_flow.get(data_name, {}).get("from_task_name", [])
    
    def get_to_task_names(self, data_name):
        return self.dag_data_flow.get(data_name, {}).get("to_task_name", [])
    
    def get_ordered_task_names(self):
        return (
            (self.ordered_tasks_name[i], self.ordered_tasks_name[i + 1] 
              if i + 1 < len(self.ordered_tasks_name) else None
            ) 
            for i in range(len(self.ordered_tasks_name))
        )


def get_register_by_name(name: str):
    return regist_map.get(name, None)


def register(name=None):
    def decorator(task_cls: type):
        task_name = getattr(task_cls, "name", getattr(task_cls, "__name__")) if name is None else name
        setattr(task_cls, "name", task_name)
        
        # 处理输入
        depends = task_cls.depends()
        outputs = task_cls.outputs()
        # 处理输出
        regist_map[task_name] = TaskRegisterInfo(task_cls=task_cls, name=task_name,
                                                 data_depends=depends, data_outputs=outputs)
        
        return task_cls
    return decorator


def get_task_run_order(head_tasks, dag_task_flow):
    ordered_tasks = list()
    done_tasks = set()
    walking_queue = deque()
    walking_queue.extend(head_tasks)
    while (walking_queue):
        task_name = walking_queue.popleft()
        if task_name in done_tasks:
            continue
        if all(
            prev_task_name in done_tasks 
            for prev_task_name in dag_task_flow.get(task_name, {}).get("prev_task_name", [])
        ):
            ordered_tasks.append(task_name)
            done_tasks.add(task_name)
            walking_queue.extend(dag_task_flow.get(task_name, {}).get("next_task_name", []))
        else:
            walking_queue.append(task_name)

    return ordered_tasks


def get_data_dag():
    head_tasks = set()
 
    tasks = list(regist_map.keys())
    dag_data_flow = {}
    
    walking_index = 0
    while walking_index < len(tasks):
        walking_task_name = tasks[walking_index]
        walking_index += 1
        walking_task = get_register_by_name(walking_task_name)
 
        walking_task_output_data_names = walking_task.get("data_outputs", [])
        for output_data_name in walking_task_output_data_names:
            dag_data_flow.setdefault(output_data_name, dict(from_task_name=[], to_task_name=[]))
            dag_data_flow[output_data_name]["from_task_name"].append(walking_task_name)
            
        walking_task_depends_data_names = walking_task.get("data_depends", [])
        for depends_data_name in walking_task_depends_data_names:
            dag_data_flow.setdefault(depends_data_name, dict(from_task_name=[], to_task_name=[]))
            dag_data_flow[depends_data_name]["to_task_name"].append(walking_task_name)
        
        if walking_task_depends_data_names == ["prof_path"]:
            head_tasks.add(walking_task_name)
 
    return dag_data_flow, head_tasks


def get_dag(exporter_names):
    head_tasks = set()
    
    dag_data_flow, _ = get_data_dag()
 
    tasks = list(exporter_names)
    dag_task_flow = {}
    
    walking_index = 0
    while walking_index < len(tasks):
        walking_task_name = tasks[walking_index]
        walking_index += 1
        walking_task = get_register_by_name(walking_task_name)
        dag_task_flow.setdefault(walking_task_name, dict(prev_task_name=[], next_task_name=[]))
 
        walking_task_depends_data_names = walking_task.get("data_depends", [])
        for depends_data_name in walking_task_depends_data_names:
            for prev_task_name in dag_data_flow.get(depends_data_name, {}).get("from_task_name", []):
                dag_task_flow[walking_task_name]["prev_task_name"].append(prev_task_name)
                dag_task_flow.setdefault(prev_task_name, dict(prev_task_name=[], next_task_name=[]))
                dag_task_flow[prev_task_name]["next_task_name"].append(walking_task_name)
                if prev_task_name not in tasks:
                    tasks.append(prev_task_name)
        
        if walking_task_depends_data_names == ["prof_path"]:
            head_tasks.add(walking_task)
    head_tasks_name = [x.name for x in head_tasks]
    ordered_tasks_name = get_task_run_order(head_tasks_name, dag_task_flow)
 
    return TaskDag(dag_data_flow, dag_task_flow, head_tasks_name, ordered_tasks_name), head_tasks


def filter_dag(dag, data_source_name):
    # 获取某个类型的输入对应的dag 图
    dag_data_flow, dag_task_flow, head_tasks_name, ordered_tasks_name = \
        dag.dag_data_flow, dag.dag_task_flow, dag.head_tasks_name, dag.ordered_tasks_name

    filterd_tasks = set([data_source_name])
    walk_tasks = list([data_source_name])
    walking_index = 0
    while walking_index < len(walk_tasks):
        walking_task_name = walk_tasks[walking_index]
        walking_index += 1
        for next_task_name in dag.get_next_task_names(walking_task_name):
            if next_task_name in filterd_tasks:
                continue
            else:
                filterd_tasks.add(next_task_name)
                walk_tasks.append(next_task_name)
    
    dag_task_flow = {k: v for k, v in dag_task_flow.items() if k in filterd_tasks}
    head_tasks_name = [data_source_name]
    ordered_tasks_name = [x for x in ordered_tasks_name if x in filterd_tasks]
    
    return TaskDag(dag_data_flow, dag_task_flow, head_tasks_name, ordered_tasks_name)
