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

import sys

import pytest
from unittest.mock import MagicMock, patch

from ms_service_metric.core.module.symbol_watcher import (
    ModuleEvent,
    ModuleEventType,
    SymbolWatchFinder,
    SymbolWatcher,
)


@pytest.fixture
def reset_singleton():
    original_instance = SymbolWatcher._instance
    original_initialized = SymbolWatcher._initialized

    yield

    SymbolWatcher._instance = original_instance
    SymbolWatcher._initialized = original_initialized


@pytest.fixture
def watcher(reset_singleton):
    SymbolWatcher._instance = None
    SymbolWatcher._initialized = False
    return SymbolWatcher()


class TestIsModuleLoaded:
    def test_given_module_in_sys_modules_when_is_module_loaded_then_returns_true(self, watcher):
        module_name = "os"
        assert module_name in sys.modules
        assert watcher.is_module_loaded(module_name) is True

    def test_given_module_not_in_sys_modules_when_is_module_loaded_then_returns_false(self, watcher):
        module_name = "non_existent_module_xyz"
        assert module_name not in sys.modules
        assert watcher.is_module_loaded(module_name) is False

    def test_given_only_submodule_in_sys_modules_when_is_module_loaded_on_parent_then_returns_false(
        self, watcher
    ):
        # Use a synthetic package path so the test works when real `vllm` is installed
        # (patch.dict only adds keys; it does not unload existing top-level modules).
        parent = "ms_metric_ut_isolated_parent"
        sub = f"{parent}.child.submod"
        with patch.dict(sys.modules, {sub: MagicMock()}):
            assert parent not in sys.modules
            assert watcher.is_module_loaded(parent) is False
            assert watcher.is_module_loaded(sub) is True

    def test_given_parent_module_in_sys_modules_when_is_module_loaded_then_returns_true(self, watcher):
        module_name = "os"
        assert module_name in sys.modules
        assert watcher.is_module_loaded(module_name) is True

    def test_given_empty_module_name_when_is_module_loaded_then_matches_root_sys_modules(self, watcher):
        assert watcher.is_module_loaded("") is ("" in sys.modules)


class TestWatchModule:
    def test_given_module_already_loaded_when_watch_module_then_callback_gets_loaded_event(self, watcher):
        callback = MagicMock()
        module_name = "os"

        watcher.watch_module(module_name, callback)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, ModuleEvent)
        assert event.module_name == module_name
        assert event.type == ModuleEventType.LOADED

    def test_given_module_not_loaded_when_watch_module_then_callback_not_called(self, watcher):
        callback = MagicMock()
        module_name = "non_existent_module_xyz_12345"

        assert module_name not in sys.modules
        watcher.watch_module(module_name, callback)
        callback.assert_not_called()


class TestGlobalCallbacks:
    def test_given_new_callback_when_watch_then_callback_registered_globally(self, watcher):
        callback = MagicMock()
        watcher.watch(callback)
        assert callback in watcher._global_callbacks

    def test_given_callback_registered_when_unwatch_then_callback_removed(self, watcher):
        callback = MagicMock()
        watcher.watch(callback)
        watcher.unwatch(callback)
        assert callback not in watcher._global_callbacks

    def test_given_global_callback_registered_when_has_global_callbacks_then_returns_true(self, watcher):
        assert watcher.has_global_callbacks() is False
        watcher.watch(MagicMock())
        assert watcher.has_global_callbacks() is True


class TestModuleEvent:
    def test_given_loaded_event_args_when_construct_then_fields_match(self):
        module = MagicMock()
        event = ModuleEvent("test.module", ModuleEventType.LOADED, module)

        assert event.module_name == "test.module"
        assert event.type == ModuleEventType.LOADED
        assert event.module is module

    def test_given_loaded_event_when_repr_then_matches_literal(self):
        event = ModuleEvent("test.module", ModuleEventType.LOADED)
        assert repr(event) == "ModuleEvent(test.module, loaded)"


class TestSymbolWatchFinder:
    def test_given_finder_when_add_target_module_then_name_in_target_set(self, watcher):
        finder = watcher._finder
        finder.add_target_module("test.module")
        assert "test.module" in finder._target_modules

    def test_given_target_registered_when_remove_target_module_then_name_removed(self, watcher):
        finder = watcher._finder
        finder.add_target_module("test.module")
        finder.remove_target_module("test.module")
        assert "test.module" not in finder._target_modules

    def test_given_global_callbacks_registered_when_should_watch_module_then_true(self, watcher):
        finder = watcher._finder
        watcher.watch(MagicMock())
        assert finder._should_watch_module("any.module") is True

    def test_given_explicit_target_module_when_should_watch_then_true(self, watcher):
        finder = watcher._finder
        finder.add_target_module("target.module")
        assert finder._should_watch_module("target.module") is True

    def test_given_submodule_of_target_when_should_watch_then_true(self, watcher):
        finder = watcher._finder
        finder.add_target_module("target.module")
        assert finder._should_watch_module("target.module.sub") is True

    def test_given_unrelated_module_when_should_watch_then_false(self, watcher):
        finder = watcher._finder
        finder.add_target_module("target.module")
        assert finder._should_watch_module("other.module") is False
