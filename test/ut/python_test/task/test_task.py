# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from unittest.mock import patch, MagicMock
import pytest
from ms_service_profiler.task.task import Task, DefaultValue, ParseError
from ms_service_profiler.task.task_register import regist_map, get_register_by_name


class MockTask(Task):
    name = "mock_task"

    @classmethod
    def depends(cls):
        return ["depend_task1", "depend_task2"]

    def run(self):
        pass


@patch('ms_service_profiler.task.task_register.get_register_by_name')
def test_task_class(mock_get_register_by_name):
    # 使用Task.register装饰器注册TestTask类
    @Task.register("test_task")
    class TestTask(Task):
        def run(self):
            pass

    # 设置get_register_by_name方法的返回值为注册的TestTask类
    mock_get_register_by_name.return_value = TestTask

    # 测试register方法
    assert TestTask.name == "test_task"
    assert regist_map["test_task"].task_cls == TestTask

    # 测试get_register_by_name方法
    result = get_register_by_name("test_task")
    assert result.task_cls == TestTask

    # 测试depends方法
    result = MockTask.depends()
    assert isinstance(result, list)
    assert result == ["depend_task1", "depend_task2"]

    # 测试set_depends_result和get_depends_result方法
    task = Task({"task_name": "test_task"})
    task.set_depends_result("depend_task1", {"data": "dummy_data"})
    result = task.get_depends_result("depend_task1")
    assert isinstance(result, dict)
    assert result == {"data": "dummy_data"}

    # 测试get_depends_result方法的异常处理
    with pytest.raises(ParseError, match='need depend_task3\'s result. but nothing found.'):
        task.get_depends_result("depend_task3")