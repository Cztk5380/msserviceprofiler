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

"""Branches in SymbolWatchFinder / SymbolWatcher (notification & finder)."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from ms_service_metric.core.module.symbol_watcher import (
    ModuleEvent,
    ModuleEventType,
    SymbolWatchFinder,
    SymbolWatcher,
)


@pytest.fixture
def iso_watcher():
    orig_i = SymbolWatcher._instance
    orig_init = SymbolWatcher._initialized
    SymbolWatcher._instance = None
    SymbolWatcher._initialized = False
    w = SymbolWatcher()
    yield w
    w.uninstall()
    SymbolWatcher._instance = orig_i
    SymbolWatcher._initialized = orig_init


def test_given_unknown_module_when_finder_find_module_then_returns_none(iso_watcher):
    assert iso_watcher._finder.find_module("x", None) is None


def test_given_module_not_in_watchlist_when_finder_find_spec_then_returns_none(iso_watcher):
    assert iso_watcher._finder.find_spec("unrelated.pkg", None, None) is None


def test_given_target_module_when_pathfinder_returns_none_then_find_spec_returns_none(iso_watcher):
    iso_watcher._finder.add_target_module("x.y")
    with patch("importlib.machinery.PathFinder.find_spec", return_value=None):
        assert iso_watcher._finder.find_spec("x.y", None, None) is None


def test_given_spec_with_no_loader_when_finder_find_spec_then_returns_same_spec(iso_watcher):
    iso_watcher._finder.add_target_module("x.y")
    spec = MagicMock()
    spec.loader = None
    with patch("importlib.machinery.PathFinder.find_spec", return_value=spec):
        assert iso_watcher._finder.find_spec("x.y", None, None) is spec


def test_given_target_loader_when_find_spec_and_exec_module_then_wraps_and_notifies(iso_watcher):
    iso_watcher._finder.add_target_module("pkg.sub")
    mock_mod = MagicMock()
    mock_mod.__name__ = "pkg.sub"

    class OrigLoader:
        def exec_module(self, module):
            pass

    spec = MagicMock()
    spec.loader = OrigLoader()

    cb = MagicMock()
    iso_watcher.watch_module("pkg.sub", cb)

    with patch("importlib.machinery.PathFinder.find_spec", return_value=spec):
        out = iso_watcher._finder.find_spec("pkg.sub", None, None)
    assert out is not None
    assert getattr(out.loader, "_symbol_watcher_wrapped", False) is True

    out.loader.exec_module(mock_mod)
    cb.assert_called()


def test_given_loader_already_wrapped_when_finder_find_spec_then_same_loader_instance(iso_watcher):
    iso_watcher._finder.add_target_module("wrapped.mod")

    class Wrapped:
        _symbol_watcher_wrapped = True

    spec = MagicMock()
    spec.loader = Wrapped()
    with patch("importlib.machinery.PathFinder.find_spec", return_value=spec):
        out = iso_watcher._finder.find_spec("wrapped.mod", None, None)
    assert out is spec
    assert out.loader is spec.loader


def test_given_immediate_watch_callback_raises_when_watch_module_then_error_swallowed(iso_watcher):
    def boom(_event):
        raise RuntimeError("immediate")

    # `os` is always loaded
    with patch.object(iso_watcher, "is_module_loaded", return_value=True):
        with patch.dict(sys.modules, {"fake_mod_immediate": MagicMock()}):
            iso_watcher.watch_module("fake_mod_immediate", boom)


def test_given_global_callback_raises_when_notify_module_loaded_then_still_tracks_module(iso_watcher):
    iso_watcher.watch(lambda _n: (_ for _ in ()).throw(RuntimeError("g")))

    iso_watcher._notify_module_loaded("fresh_mod_notify_test")
    assert "fresh_mod_notify_test" in iso_watcher._loaded_modules


def test_given_per_module_callback_raises_when_notify_module_loaded_then_no_raise(iso_watcher):

    def bad(_e):
        raise RuntimeError("m")

    iso_watcher.watch_module("solo_mod_cb", bad)
    with patch.dict(sys.modules, {"solo_mod_cb": MagicMock()}):
        iso_watcher._notify_module_loaded("solo_mod_cb")


def test_given_module_tracked_when_notify_unloaded_then_callback_gets_unloaded_event(iso_watcher):
    cb = MagicMock()
    iso_watcher.watch_module("mod_unload_ut", cb)
    iso_watcher._loaded_modules.add("mod_unload_ut")
    iso_watcher._notify_module_unloaded("mod_unload_ut")
    event = cb.call_args[0][0]
    assert event.type == ModuleEventType.UNLOADED


def test_given_watcher_when_start_twice_then_single_meta_path_entry_uninstall_removes(iso_watcher):
    iso_watcher.start()
    try:
        iso_watcher.start()
        assert iso_watcher._finder in sys.meta_path
    finally:
        iso_watcher.uninstall()
    assert iso_watcher._finder not in sys.meta_path
    iso_watcher.uninstall()


def test_given_inner_loader_create_module_when_wrapped_create_module_then_delegates(iso_watcher):
    iso_watcher._finder.add_target_module("delegating.mod")
    calls = []

    class Inner:
        def create_module(self, mod_spec):
            calls.append(mod_spec)
            return None

        def exec_module(self, module):
            pass

    spec = MagicMock()
    spec.loader = Inner()
    with patch("importlib.machinery.PathFinder.find_spec", return_value=spec):
        out = iso_watcher._finder.find_spec("delegating.mod", None, None)
    sm = MagicMock()
    out.loader.create_module(sm)
    assert calls == [sm]
