# -------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
# -------------------------------------------------------------------------

"""HookController 单元测试：针对 c03de41 动态 hook 替换特性补充覆盖率。"""

from unittest.mock import Mock, MagicMock, patch
import pytest

from ms_service_profiler.patcher.core.config_loader import MetricsConfig, ProfilingConfig
from ms_service_profiler.patcher.core.hook_controller import HookController
from ms_service_profiler.patcher.core.symbol_watcher import SymbolWatchFinder


@pytest.fixture
def mock_watcher():
    """提供模拟的 SymbolWatchFinder。"""
    w = MagicMock(spec=SymbolWatchFinder)
    w.load_handlers = MagicMock()
    w.check_and_apply_existing_modules = MagicMock()
    w.apply_all_hooks = MagicMock(return_value=[MagicMock(), MagicMock()])
    w.set_auto_apply = MagicMock()
    w.get_applied_hookers = MagicMock(return_value=[])
    return w


@pytest.fixture
def hook_controller(mock_watcher):
    """提供 HookController 实例。"""
    return HookController(mock_watcher)


class TestHookControllerInit:
    """测试 HookController 初始化与属性。"""

    def test_init(self, mock_watcher):
        ctrl = HookController(mock_watcher)
        assert ctrl._watcher is mock_watcher
        assert ctrl._enabled is False

    def test_enabled_property_false(self, hook_controller):
        assert hook_controller.enabled is False

    def test_enabled_property_true(self, hook_controller):
        hook_controller._enabled = True
        assert hook_controller.enabled is True


class TestHookControllerEnable:
    """测试 enable 方法。"""

    def test_enable_success_first_time(self, hook_controller, mock_watcher):
        handlers = {"mod:func": [MagicMock(), MagicMock()]}
        profiling_config = ProfilingConfig(concrete=handlers)
        mock_watcher.apply_all_hooks.return_value = [MagicMock(), MagicMock()]

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.enable(profiling_handlers=profiling_config, metrics_handlers=None)

        assert n == 2
        assert hook_controller._enabled is True
        mock_watcher.load_handlers.assert_called_once()
        call_kw = mock_watcher.load_handlers.call_args[1]
        assert call_kw["profiling_handlers"] is profiling_config
        assert call_kw["hooks_enabled"] is False
        mock_watcher.check_and_apply_existing_modules.assert_called_once()
        mock_watcher.apply_all_hooks.assert_called_once()
        mock_watcher.set_auto_apply.assert_called_once_with(True)

    def test_enable_reload_when_already_enabled(self, hook_controller, mock_watcher):
        hook_controller._enabled = True
        handlers = {"mod:func": [MagicMock()]}
        current_profiling = ProfilingConfig(concrete=handlers)
        mock_watcher.get_current_profiling_handlers.return_value = current_profiling
        mock_watcher.get_current_metrics_handlers.return_value = MetricsConfig()
        mock_watcher.apply_all_hooks.return_value = [MagicMock()]

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.enable(profiling_handlers=current_profiling, metrics_handlers=None)

        assert n == 1
        mock_watcher.load_handlers.assert_called_once()
        call_kw = mock_watcher.load_handlers.call_args[1]
        assert call_kw["profiling_handlers"] is current_profiling
        assert call_kw["hooks_enabled"] is True

    def test_enable_empty_config(self, hook_controller, mock_watcher):
        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.enable(profiling_handlers=ProfilingConfig(), metrics_handlers=None)

        assert n == 0
        assert hook_controller._enabled is False
        mock_watcher.load_handlers.assert_not_called()
        mock_watcher.apply_all_hooks.assert_not_called()

    def test_enable_none_config(self, hook_controller, mock_watcher):
        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.enable(profiling_handlers=None, metrics_handlers=None)

        assert n == 0
        mock_watcher.load_handlers.assert_not_called()

    def test_enable_exception(self, hook_controller, mock_watcher):
        handlers = {"mod:func": [MagicMock()]}
        mock_watcher.load_handlers.side_effect = RuntimeError("load error")

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.enable(
                profiling_handlers=ProfilingConfig(concrete=handlers), metrics_handlers=None
            )

        assert n == 0
        assert hook_controller._enabled is False


class TestHookControllerDisable:
    """测试 disable 方法。"""

    def test_disable_when_not_enabled(self, hook_controller, mock_watcher):
        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.disable()

        assert n == 0
        mock_watcher.set_auto_apply.assert_not_called()
        mock_watcher.get_applied_hookers.assert_not_called()

    def test_disable_success(self, hook_controller, mock_watcher):
        hook_controller._enabled = True
        hook_helper = MagicMock()
        mock_hooker = MagicMock()
        mock_hooker.hooks = [hook_helper]
        mock_watcher.get_applied_hookers.return_value = [mock_hooker]

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.disable()

        assert n == 1
        assert hook_controller._enabled is False
        mock_watcher.set_auto_apply.assert_called_once_with(False)
        hook_helper.recover.assert_called_once()

    def test_disable_recover_exception(self, hook_controller, mock_watcher):
        hook_controller._enabled = True
        hook_helper = MagicMock()
        hook_helper.recover.side_effect = RuntimeError("recover error")
        mock_hooker = MagicMock()
        mock_hooker.hooks = [hook_helper]
        mock_watcher.get_applied_hookers.return_value = [mock_hooker]

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.disable()

        assert n == 0
        assert hook_controller._enabled is False

    def test_disable_exception(self, hook_controller, mock_watcher):
        hook_controller._enabled = True
        mock_watcher.get_applied_hookers.side_effect = RuntimeError("get error")

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            n = hook_controller.disable()

        assert n == 0
        # 异常时 disable 未完成，状态保持 enabled
        assert hook_controller._enabled is True


class TestHookControllerGetCallbacks:
    """测试 get_callbacks 方法。"""

    def test_get_callbacks_returns_two_callables(self, hook_controller):
        load_config = Mock(return_value=[])
        on_start, on_stop = hook_controller.get_callbacks(load_config)

        assert callable(on_start)
        assert callable(on_stop)

    def test_on_start_callback_calls_enable(self, hook_controller, mock_watcher):
        handlers = {"mod:func": [MagicMock()]}
        profiling_config = ProfilingConfig(concrete=handlers)
        get_handlers = Mock(return_value=profiling_config)
        mock_watcher.apply_all_hooks.return_value = [MagicMock()]

        on_start, _ = hook_controller.get_callbacks(get_handlers)

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            on_start()

        get_handlers.assert_called_once()
        mock_watcher.load_handlers.assert_called_once()
        call_kw = mock_watcher.load_handlers.call_args[1]
        assert call_kw["profiling_handlers"].concrete == handlers
        assert call_kw["metrics_handlers"] is None
        assert call_kw["hooks_enabled"] is False

    def test_on_stop_callback_calls_disable(self, hook_controller, mock_watcher):
        hook_controller._enabled = True
        mock_watcher.get_applied_hookers.return_value = []

        _, on_stop = hook_controller.get_callbacks(Mock())

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            on_stop()

        mock_watcher.set_auto_apply.assert_called_once_with(False)

    def test_on_start_callback_exception(self, hook_controller, mock_watcher):
        load_config = Mock(side_effect=RuntimeError("config error"))
        on_start, _ = hook_controller.get_callbacks(load_config)

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            on_start()

        # 不应抛出，仅记录日志
        assert hook_controller._enabled is False

    def test_on_stop_callback_exception(self, hook_controller, mock_watcher):
        hook_controller._enabled = True
        mock_watcher.get_applied_hookers.side_effect = RuntimeError("get error")
        _, on_stop = hook_controller.get_callbacks(Mock())

        with patch("ms_service_profiler.patcher.core.hook_controller.logger"):
            on_stop()

        assert hook_controller._enabled is True
