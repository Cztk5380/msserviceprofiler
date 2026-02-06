# -------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
# -------------------------------------------------------------------------

"""SymbolWatchFinder 单元测试：针对 c03de41 动态 hook 中 load/recover/set_auto_apply 等逻辑补充覆盖率。"""

from unittest.mock import Mock, MagicMock, patch
import pytest

from ms_service_profiler.patcher.core.symbol_watcher import SymbolWatchFinder


@pytest.fixture
def watcher():
    return SymbolWatchFinder()


class TestSetAutoApplyAndGetAppliedHookers:
    """测试 set_auto_apply 与 get_applied_hookers。"""

    def test_set_auto_apply_true(self, watcher):
        watcher.set_auto_apply(True)
        assert watcher._auto_apply_enabled is True

    def test_set_auto_apply_false(self, watcher):
        watcher.set_auto_apply(False)
        assert watcher._auto_apply_enabled is False

    def test_get_applied_hookers_empty(self, watcher):
        result = watcher.get_applied_hookers()
        assert result == []

    def test_get_applied_hookers_returns_copy(self, watcher):
        hooker = MagicMock()
        watcher._applied_hookers.append(hooker)
        result = watcher.get_applied_hookers()
        assert result == [hooker]
        assert result is not watcher._applied_hookers


class TestRecoverHookersForSymbols:
    """测试 recover_hookers_for_symbols。"""

    def test_recover_empty_symbols(self, watcher):
        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.recover_hookers_for_symbols(set())

    def test_recover_symbol_not_in_mapping(self, watcher):
        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.recover_hookers_for_symbols({"unknown.module:func"})

    def test_recover_symbol_in_mapping_applied(self, watcher):
        hook_helper = MagicMock()
        hooker = MagicMock()
        hooker.hooks = [hook_helper]
        watcher._symbol_to_hooker["mod:func"] = hooker
        watcher._applied_hookers.append(hooker)

        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.recover_hookers_for_symbols({"mod:func"})

        hook_helper.recover.assert_called_once()

    def test_recover_symbol_in_mapping_not_applied(self, watcher):
        hooker = MagicMock()
        watcher._symbol_to_hooker["mod:func"] = hooker
        # hooker 不在 _applied_hookers 中

        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.recover_hookers_for_symbols({"mod:func"})

        hooker.hooks  # 可能未定义，不应 recover
        # 仅验证不抛异常

    def test_recover_exception_in_recover(self, watcher):
        hook_helper = MagicMock()
        hook_helper.recover.side_effect = RuntimeError("recover error")
        hooker = MagicMock()
        hooker.hooks = [hook_helper]
        watcher._symbol_to_hooker["mod:func"] = hooker
        watcher._applied_hookers.append(hooker)

        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.recover_hookers_for_symbols({"mod:func"})

        # 仅记录错误，不抛出


class TestLoadSymbolConfigRemovedSymbols:
    """测试 load_symbol_config 中“删除的 symbol”分支（hooks_enabled 与恢复逻辑）。"""

    def test_load_config_first_time_no_removed(self, watcher):
        config = [{"symbol": "a.b:func1"}, {"symbol": "c.d:func2"}]
        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.load_symbol_config(config)

        assert watcher._config_loaded is True
        assert len(watcher._symbol_hooks) == 2
        assert "symbol_0" in watcher._symbol_hooks
        assert watcher._symbol_hooks["symbol_0"]["symbol"] == "a.b:func1"

    def test_load_config_invalid_entry_not_dict(self, watcher):
        config = [{"symbol": "a:func"}, "not_a_dict"]
        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.load_symbol_config(config)

        assert len(watcher._symbol_hooks) == 1

    def test_load_config_missing_symbol_key(self, watcher):
        config = [{"symbol": "a:func"}, {"domain": "Test"}]
        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.load_symbol_config(config)

        assert len(watcher._symbol_hooks) == 1

    def test_load_config_removed_symbols_hooks_disabled(self, watcher):
        watcher._config_loaded = True
        watcher._applied_hooks = {"old.mod:func"}
        hooker = MagicMock()
        watcher._symbol_to_hooker["old.mod:func"] = hooker
        watcher._prepared_hookers = [hooker]
        watcher._applied_hookers = [hooker]

        new_config = [{"symbol": "new.mod:func2"}]

        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.load_symbol_config(new_config, hooks_enabled=False)

        assert "old.mod:func" not in watcher._symbol_to_hooker
        assert "old.mod:func" not in watcher._applied_hooks
        assert hooker not in watcher._prepared_hookers
        assert hooker not in watcher._applied_hookers

    def test_load_config_removed_symbols_hooks_enabled_recover(self, watcher):
        watcher._config_loaded = True
        watcher._applied_hooks = {"old.mod:func"}
        hook_helper = MagicMock()
        hooker = MagicMock()
        hooker.hooks = [hook_helper]
        watcher._symbol_to_hooker["old.mod:func"] = hooker
        watcher._prepared_hookers = [hooker]
        watcher._applied_hookers = [hooker]

        new_config = [{"symbol": "new.mod:func2"}]

        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher.load_symbol_config(new_config, hooks_enabled=True)

        hook_helper.recover.assert_called_once()
        assert "old.mod:func" not in watcher._symbol_to_hooker
        assert hooker not in watcher._applied_hookers


class TestLoadSymbolConfigPrepareHooks:
    """测试 load 后 _prepare_single_symbol_hook 相关分支（通过 check_and_apply 或 find_spec 间接）。"""

    def test_prepare_symbol_hooks_for_module_exception(self, watcher):
        watcher._symbol_hooks = {"symbol_0": {"symbol": "mod:func"}}
        watcher._config_loaded = True

        with patch.object(
            watcher, "_prepare_single_symbol_hook", side_effect=RuntimeError("prepare error")
        ), patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            watcher._prepare_symbol_hooks_for_module(
                "mod", [("symbol_0", {"symbol": "mod:func"})]
            )


class TestParseSymbolPathAndBuildHookPoints:
    """测试 _parse_symbol_path 与 _build_hook_points。"""

    def test_parse_symbol_path_class_method(self, watcher):
        module_path, method_name, class_name = watcher._parse_symbol_path("mod.path:ClassName.method_name")
        assert module_path == "mod.path"
        assert method_name == "method_name"
        assert class_name == "ClassName"

    def test_parse_symbol_path_function_only(self, watcher):
        module_path, method_name, class_name = watcher._parse_symbol_path("mod:function_name")
        assert module_path == "mod"
        assert method_name == "function_name"
        assert class_name is None

    def test_build_hook_points_with_class(self, watcher):
        points = watcher._build_hook_points("mod", "method_name", "ClassName")
        assert points == [("mod", "ClassName.method_name")]

    def test_build_hook_points_without_class(self, watcher):
        points = watcher._build_hook_points("mod", "func", None)
        assert points == [("mod", "func")]


class TestCreateHandlerFunction:
    """测试 _create_handler_function。"""

    def test_create_handler_no_handler_uses_default_timer(self, watcher):
        with patch("ms_service_profiler.patcher.core.symbol_watcher.make_default_time_hook") as mock_make:
            mock_make.return_value = MagicMock()
            result = watcher._create_handler_function(
                {"symbol": "mod:func", "domain": "D", "name": "N"}, "func"
            )
            mock_make.assert_called_once_with(domain="D", name="N", attributes=None)
            assert result == mock_make.return_value

    def test_create_handler_custom_handler(self, watcher):
        with patch("ms_service_profiler.patcher.core.symbol_watcher.importlib.import_module") as mock_import:
            mock_mod = MagicMock()
            mock_mod.handler_func = MagicMock()
            mock_import.return_value = mock_mod
            result = watcher._create_handler_function(
                {"symbol": "mod:func", "handler": "some.module:handler_func"}, "func"
            )
            mock_import.assert_called_once_with("some.module")
            assert result == mock_mod.handler_func


class TestApplyAllHooks:
    """测试 apply_all_hooks。"""

    def test_apply_all_hooks_empty(self, watcher):
        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            result = watcher.apply_all_hooks()
        assert result == []
        assert watcher._auto_apply_enabled is True

    def test_apply_all_hooks_one_success(self, watcher):
        hooker = MagicMock()
        watcher._prepared_hookers = [hooker]

        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            result = watcher.apply_all_hooks()

        hooker.init.assert_called_once()
        assert len(result) == 1
        assert hooker in result

    def test_apply_all_hooks_one_fails(self, watcher):
        hooker = MagicMock()
        hooker.init.side_effect = RuntimeError("init error")
        watcher._prepared_hookers = [hooker]

        with patch("ms_service_profiler.patcher.core.symbol_watcher.logger"):
            result = watcher.apply_all_hooks()

        assert result == []


class TestIsTargetSymbol:
    """测试 _is_target_symbol。"""

    def test_config_not_loaded(self, watcher):
        assert watcher._is_target_symbol("any.module") is False

    def test_direct_match(self, watcher):
        watcher._config_loaded = True
        watcher._symbol_hooks = {"s0": {"symbol": "mod.path:func"}}
        assert watcher._is_target_symbol("mod.path") is True

    def test_parent_package_match(self, watcher):
        watcher._config_loaded = True
        watcher._symbol_hooks = {"s0": {"symbol": "parent.child.grand:func"}}
        assert watcher._is_target_symbol("parent") is True
        assert watcher._is_target_symbol("parent.child") is True

    def test_no_match(self, watcher):
        watcher._config_loaded = True
        watcher._symbol_hooks = {"s0": {"symbol": "other.mod:func"}}
        assert watcher._is_target_symbol("some.other") is False
