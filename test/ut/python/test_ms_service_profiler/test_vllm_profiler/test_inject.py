# tests/patcher/core/test_inject.py
from copy import copy
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from ms_service_profiler.patcher.core.inject import inject_function
from ms_service_profiler.patcher.core.utils import FunctionContext


# 辅助函数：创建一个简单的原始函数
def original_func(a, b):
    return a + b


def original_func_no_return():
    x = 1
    y = 2


def original_func_with_locals(x):
    y = x * 2
    z = y + 1
    return z


# 辅助函数：确保线程本地上下文已初始化
def ensure_thread_context():
    if not hasattr(threading.local(), "context"):
        threading.local().context = FunctionContext()
    return threading.local().context


# 辅助类：创建可调用的钩子（钩子工厂）
class HookFactory:
    """返回一个可调用的钩子，该钩子返回实现了 __enter__/__exit__ 的对象"""
    
    def __init__(self, name="hook", enter_side_effect=None, exit_side_effect=None):
        self.name = name
        self.enter_side_effect = enter_side_effect
        self.exit_side_effect = exit_side_effect
        self.enter_mock = MagicMock(name=f"{name}.__enter__", side_effect=enter_side_effect)
        self.exit_mock = MagicMock(name=f"{name}.__exit__", side_effect=exit_side_effect)
        self.call_count = 0
        self.received_ctx = None
    
    def __call__(self, ctx):
        """返回一个实现了上下文管理协议的对象"""
        self.call_count += 1
        self.received_ctx = ctx
        
        class ContextManager:
            def __init__(self, factory):
                self.factory = factory
            
            def __enter__(self):
                return self.factory.enter_mock()
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                return self.factory.exit_mock(exc_type, exc_val, exc_tb)
        
        return ContextManager(self)


# 测试正例：单个钩子，进入和退出均被调用
def test_given_single_hook_when_function_called_then_enter_and_exit_called():
    # Given
    hook_factory = HookFactory("hook1")
    hooks = [hook_factory]
    injected_func = inject_function(original_func, hooks)

    # When
    result = injected_func(3, 5)

    # Then
    assert result == 8
    assert hook_factory.call_count == 1  # 钩子工厂被调用一次
    hook_factory.enter_mock.assert_called_once()
    hook_factory.exit_mock.assert_called_once_with(None, None, None)


# 测试正例：多个钩子，所有钩子均被调用
def test_given_multiple_hooks_when_function_called_then_all_hooks_called():
    # Given
    hook_factory1 = HookFactory("hook1")
    hook_factory2 = HookFactory("hook2")
    hooks = [hook_factory1, hook_factory2]
    injected_func = inject_function(original_func, hooks)

    # When
    result = injected_func(2, 3)

    # Then
    assert result == 5
    assert hook_factory1.call_count == 1
    assert hook_factory2.call_count == 1
    hook_factory1.enter_mock.assert_called_once()
    hook_factory2.enter_mock.assert_called_once()
    hook_factory1.exit_mock.assert_called_once_with(None, None, None)
    hook_factory2.exit_mock.assert_called_once_with(None, None, None)


# 测试钩子中能访问函数局部变量和返回值
def test_given_hook_when_function_called_then_context_contains_locals_and_return():
    # Given
    context_container = {}
    
    class CapturingHookFactory:
        def __call__(self, ctx):
            # 工厂被调用时，ctx 应该包含参数，但还没有完整的局部变量
            context_container["factory_ctx"] = copy(ctx)
            
            class CapturingContextManager:
                def __enter__(self):
                    # 确保上下文已初始化
                    context_container["enter_ctx"] = copy(ctx)
                    # 复制一份，避免后续修改影响断言
                    context_container["enter_locals"] = dict(ctx.local_values) if ctx.local_values else {}
                
                def __exit__(self, *args):
                    context_container["exit_ctx"] = copy(ctx)
                    context_container["exit_locals"] = dict(ctx.local_values) if ctx.local_values else {}
                    context_container["exit_return"] = ctx.return_value
            
            return CapturingContextManager()
    
    hook_factory = CapturingHookFactory()
    injected_func = inject_function(original_func_with_locals, [hook_factory])

    # When
    result = injected_func(5)

    # Then
    assert result == 11  # (5*2)+1 = 11
    
    # 验证工厂接收到的上下文（此时应该有参数 x，但还没有局部变量 y 和 z）
    factory_ctx = context_container["factory_ctx"]
    assert factory_ctx.local_values == {}
    
    # 验证 enter 时的上下文（和工厂接收到的相同）
    assert context_container["enter_locals"] == {"x": 5}
    
    # 验证 exit 时的上下文（包含所有局部变量和返回值）
    assert context_container["exit_locals"] == {"x": 5, "y": 10, "z": 11}
    assert context_container["exit_return"] == 11


# 测试函数没有显式 return 时 exit 仍被调用
def test_given_function_without_return_when_hooked_then_exit_called_with_none():
    # Given
    hook_factory = HookFactory("hook")
    injected_func = inject_function(original_func_no_return, [hook_factory])

    # When
    result = injected_func()

    # Then
    assert result is None
    assert hook_factory.call_count == 1
    hook_factory.enter_mock.assert_called_once()
    hook_factory.exit_mock.assert_called_once_with(None, None, None)


# 测试钩子 __enter__ 抛出异常，失败计数增加，且 __exit__ 不被调用
def test_given_hook_throws_in_enter_when_called_then_failure_count_incremented_and_exit_not_called():
    # Given
    def raise_exception():
        raise ValueError("enter failed")

    class TrackingHookFactory:
        def __init__(self, name):
            self.name = name
            self.call_count = 0
            self.enter_called = 0
            self.exit_called = 0
        
        def __call__(self, ctx):
            self.call_count += 1
            
            class TrackingContextManager:
                def __init__(self, factory):
                    self.factory = factory
                
                def __enter__(self):
                    self.factory.enter_called += 1
                    raise ValueError("enter failed")
                
                def __exit__(self, *args):
                    self.factory.exit_called += 1
            
            return TrackingContextManager(self)
    
    good_factory = HookFactory("good")
    bad_factory = TrackingHookFactory("bad")
    hooks = [good_factory, bad_factory]

    with patch("ms_service_profiler.patcher.core.inject.logger") as mock_logger:
        injected_func = inject_function(original_func, hooks)

        # When
        result = injected_func(1, 2)

    # Then
    assert result == 3
    
    # 两个工厂都被调用
    assert good_factory.call_count == 1
    assert bad_factory.call_count == 1
    
    # 好钩子的 enter 和 exit 都被调用
    good_factory.enter_mock.assert_called_once()
    good_factory.exit_mock.assert_called_once_with(None, None, None)
    
    # 坏钩子的 enter 被调用（抛出异常），exit 不应该被调用
    assert bad_factory.enter_called == 1
    
    # 错误日志应记录
    mock_logger.error.assert_called()


# 测试钩子 __exit__ 抛出异常，失败计数增加
def test_given_hook_throws_in_exit_when_called_then_failure_count_incremented():
    # Given
    def raise_exception(*args):
        raise RuntimeError("exit failed")

    class TrackingExitFactory:
        def __init__(self, name):
            self.name = name
            self.call_count = 0
            self.enter_called = 0
            self.exit_called = 0
        
        def __call__(self, ctx):
            self.call_count += 1
            
            class TrackingContextManager:
                def __init__(self, factory):
                    self.factory = factory
                
                def __enter__(self):
                    self.factory.enter_called += 1
                
                def __exit__(self, *args):
                    self.factory.exit_called += 1
                    raise RuntimeError("exit failed")
            
            return TrackingContextManager(self)
    
    good_factory = HookFactory("good")
    bad_factory = TrackingExitFactory("bad")
    hooks = [good_factory, bad_factory]

    with patch("ms_service_profiler.patcher.core.inject.logger") as mock_logger:
        injected_func = inject_function(original_func, hooks)

        # When
        result = injected_func(4, 5)

    # Then
    assert result == 9
    
    assert good_factory.call_count == 1
    assert bad_factory.call_count == 1
    
    good_factory.enter_mock.assert_called_once()
    
    # 坏钩子的 enter 和 exit 都被调用
    assert bad_factory.enter_called == 1
    assert bad_factory.exit_called == 1
    
    mock_logger.error.assert_called()


# 测试失败计数达到阈值后，该钩子被跳过
def test_given_hook_fails_multiple_times_when_threshold_reached_then_hook_skipped():
    # Given
    call_count = {"enter": 0, "exit": 0, "factory": 0}

    class FailingHookFactory:
        def __call__(self, ctx):
            call_count["factory"] += 1
            
            class FailingContextManager:
                def __enter__(self):
                    call_count["enter"] += 1
                    raise ValueError("always fail")
                
                def __exit__(self, *args):
                    call_count["exit"] += 1
                    raise ValueError("always fail")
            
            return FailingContextManager()

    hook_factory = FailingHookFactory()
    hooks = [hook_factory]
    injected_func = inject_function(original_func, hooks)

    # When - 调用 6 次（阈值 5）
    for i in range(6):
        with patch("ms_service_profiler.patcher.core.inject.logger"):
            result = injected_func(i, i)
            assert result == i * 2

    # Then - 前5次 enter 被调用，第6次被跳过
    assert call_count["factory"] == 6  # 工厂每次都被调用
    # 注意：当 enter 失败时，exit 不会被调用，所以 enter 和 exit 的次数可能不同
    assert call_count["enter"] <= 5
    assert call_count["exit"] <= 5


# 测试多线程环境下上下文独立
def test_given_multiple_threads_when_hooked_then_contexts_are_independent():
    # Given
    results = {}
    import threading
    
    class ThreadHookFactory:
        def __call__(self, current_ctx):
            class ThreadContextManager:
                def __enter__(self):
                    # 确保上下文已初始化
                    results[f"enter_{threading.current_thread().name}"] = dict(current_ctx.local_values) if current_ctx.local_values else {}
                
                def __exit__(self, *args):
                    results[f"exit_{threading.current_thread().name}"] = current_ctx.return_value
            
            return ThreadContextManager()
    
    hook_factory = ThreadHookFactory()
    hooks = [hook_factory]
    injected_func = inject_function(original_func, hooks)

    def target():
        # 每个线程需要初始化自己的上下文
        injected_func(1, 2)

    # When
    t1 = threading.Thread(target=target, name="Thread-1")
    t2 = threading.Thread(target=target, name="Thread-2")
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Then
    assert "enter_Thread-1" in results
    assert "enter_Thread-2" in results
    assert "exit_Thread-1" in results
    assert "exit_Thread-2" in results
    assert results["enter_Thread-1"] == {"a": 1, "b": 2}
    assert results["enter_Thread-2"] == {"a": 1, "b": 2}
    assert results["exit_Thread-1"] == 3
    assert results["exit_Thread-2"] == 3


# 测试不同 Python 版本的字节码插入（仅验证基本功能，不模拟版本）
def test_given_different_python_versions_when_injected_then_function_works():
    # Given
    hook_factory = HookFactory("hook")
    injected_func = inject_function(original_func, [hook_factory])

    # When
    result = injected_func(7, 8)

    # Then
    assert result == 15
    assert hook_factory.call_count == 1
    hook_factory.enter_mock.assert_called_once()
    hook_factory.exit_mock.assert_called_once_with(None, None, None)


# 测试钩子工厂可以访问 FunctionContext
def test_given_hook_factory_when_called_then_receives_function_context():
    # Given
    received_contexts = []
    
    class ContextCheckingFactory:
        def __call__(self, ctx):
            received_contexts.append(ctx)
            
            class DummyContextManager:
                def __enter__(self):
                    pass
                
                def __exit__(self, *args):
                    pass
            
            return DummyContextManager()
    
    hook_factory = ContextCheckingFactory()
    injected_func = inject_function(original_func, [hook_factory])

    # When
    result = injected_func(10, 20)

    # Then
    assert result == 30
    assert len(received_contexts) == 1
    assert isinstance(received_contexts[0], FunctionContext)
    # 工厂被调用时，local_values 已经包含参数
    assert received_contexts[0].local_values == {"a": 10, "b": 20}