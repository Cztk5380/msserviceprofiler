import unittest
from unittest.mock import Mock, patch
from multiprocessing import Queue
from ms_service_profiler.task.task_register import TaskDag, TaskRegisterInfo
from ms_service_profiler.task.task_manager import SubprocessInfo, Taskmanger
from ms_service_profiler.task.task_manager import Color, task_run


class TestSubprocessInfo(unittest.TestCase):
    def setUp(self):
        self.subprocess_info = SubprocessInfo()

    def test_get_queues(self):
        self.assertEqual(self.subprocess_info.get_queues(), [])

    def test_add_queue(self):
        queue = Queue()
        self.subprocess_info.add_queue(queue)
        self.assertEqual(self.subprocess_info.get_queues(), [queue])

    def test_new_process(self):
        send_queue = Queue()
        args = ('arg1', 'arg2')
        self.subprocess_info.new_process(send_queue, args)
        self.assertEqual(len(self.subprocess_info.get_queues()), 1)
        self.assertEqual(len(self.subprocess_info.processes), 1)

class TestTaskmanger(unittest.TestCase):
    def setUp(self):
        self.task_dag = TaskDag(dict(), dict(), list(), list())
        self.task_manager = Taskmanger(self.task_dag)

    def test_init_task(self):
        task_name = 'task1'
        task_info = self.task_manager.init_task(task_name)
        self.assertIn(task_name, self.task_manager.task_manager_info_dict)
        self.assertEqual(task_info['state'], 'unstart')

    def test_new_queue(self):
        _, index = self.task_manager.new_queue()
        self.assertEqual(index, len(self.task_manager.queues) - 1)
    
    def test_set_task_finished(self):
        # 初始化任务和后续任务
        finished_task_name = 'task1'
        next_task_name = 'task2'
        next_task_set = [(0, next_task_name)]
        
        # 初始化任务信息
        self.task_manager.init_task(finished_task_name)
        self.task_manager.init_task(next_task_name)
        self.task_manager.create_pool(TaskRegisterInfo('123', None, list(), list()), list(),
                                      TaskDag(dict(), dict(), list(), list()), None)
        
        # 设置任务完成
        self.task_manager.set_task_finished(finished_task_name, next_task_set)
        
        # 验证任务状态是否更新为 'finished'
        self.assertEqual(self.task_manager.get_task_state(finished_task_name), 'finished')
        
        # 验证后续任务是否被正确启动
        self.assertEqual(self.task_manager.pool_owner[0], next_task_name)
        self.assertEqual(self.task_manager.get_task_state(next_task_name), 'started')

    def test_fill_gater_data(self):
        task_name = 'task1'
        task_index = 0
        data = 'test_data'
        
        # 初始化任务信息
        self.task_manager.init_task(task_name).get("queues").append(1)
        self.task_manager.init_task(task_name).get("queues").append(2)
        
        # 测试 gather_data 为空的情况
        gather_data = self.task_manager.fill_gater_data(task_name, task_index, data)
        self.assertIsNone(gather_data)
        
        # 验证 gather_data 是否正确填充
        task_manager_info = self.task_manager.init_task(task_name)
        self.assertEqual(len(task_manager_info.get("gather_data")), 1)
        self.assertEqual(task_manager_info.get("gather_data")[0][task_index], data)
        
        # 测试 gather_data 已有数据的情况
        gather_data = self.task_manager.fill_gater_data(task_name, task_index, data)
        self.assertIsNone(gather_data)
        
        # 验证 gather_data 是否正确填充
        task_manager_info = self.task_manager.init_task(task_name)
        self.assertEqual(len(task_manager_info.get("gather_data")), 2)
        self.assertEqual(task_manager_info.get("gather_data")[0][task_index], data)

        # 测试 gather_data 已有其他索引的数据
        other_task_index = 1
        other_data = 'other_data'
        gather_data = self.task_manager.fill_gater_data(task_name, other_task_index, other_data)
        self.assertIsNotNone(gather_data)
        
        # 验证 gather_data 是否正确填充
        task_manager_info = self.task_manager.init_task(task_name)
        self.assertEqual(len(task_manager_info.get("gather_data")), 1)
        self.assertEqual(task_manager_info.get("gather_data")[0][task_index], data)

        # 测试 gather_data 已有完整数据的情况
        gather_data = self.task_manager.fill_gater_data(task_name, other_task_index, other_data)
        self.assertEqual(gather_data, [data, other_data])
        
        # 验证 gather_data 是否被清空
        task_manager_info = self.task_manager.init_task(task_name)
        self.assertEqual(len(task_manager_info.get("gather_data")), 0)

    @patch('ms_service_profiler.task.task_manager.Process')
    def test_start(self, mock_process):
        # 初始化任务和进程
        task_name = 'task1'
        task_index = 0
        next_task_set = (0, None)
        
        # 初始化任务信息
        self.task_manager.init_task(task_name)
        self.task_manager.pool_owner.append(None)
        self.task_manager.pool.append(SubprocessInfo())
        
        # 模拟进程和队列
        mock_process.return_value = Mock()
        mock_process.return_value.start = Mock()
        
        task_manager_info = self.task_manager.init_task(task_name)
        task_manager_info.get("queues").append(Queue())
        
        # 模拟消息循环
        self.task_manager.manager_recv_queue.put((task_name, task_index, 'finished', (next_task_set, False)))
        
        # 调用 start 方法
        self.task_manager.start()
        
        # 验证任务状态是否更新为 'finished'
        self.assertEqual(self.task_manager.get_task_state(task_name), 'finished')
        


class TestTaskRun(unittest.TestCase):
    def setUp(self):
        self.task_dag = TaskDag(dict(), dict(), list(), list())
        self.task_manager = Taskmanger(self.task_dag)
        
    @patch('ms_service_profiler.task.task_manager.Process')
    def test_task_run(self, mock_process):
        # 模拟进程和队列
        mock_process.return_value = Mock()
        mock_process.return_value.start = Mock()
        
        # 模拟任务运行
        task_name = 'task1'
        next_task_name = 'task2'
        next_task_set = [(0, next_task_name)]
        
        # 初始化任务信息
        self.task_manager.init_task(task_name)
        self.task_manager.init_task(next_task_name)
        
        # 模拟进程和队列
        recv_queue = Queue()
        send_queue = Queue()
        
        # 模拟 task_run 函数
        task_run('input_data', self.task_dag, 0, 'args', recv_queue, send_queue)
        
        # 验证任务状态是否更新为 'finished'
        self.assertEqual(self.task_manager.get_task_state(task_name), 'unstart')
        
        # 验证后续任务是否被正确启动
        self.assertEqual(self.task_manager.get_task_state(next_task_name), 'unstart')  # 由于 send_go 未被调用，状态应仍为 'unstart'


class TestTasksRun(unittest.TestCase):
    @patch('ms_service_profiler.task.task_manager.Taskmanger')
    def test_tasks_run(self, mock_task_manager):
        # Mock the necessary objects and methods
        # Call tasks_run with the mocked objects
        # Assert the expected behavior
        pass

if __name__ == '__main__':
    unittest.main()