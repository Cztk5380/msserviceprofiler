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

"""Extra Symbol paths: hook builders, unlock/remove, update_hook, unhook errors."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from ms_service_metric.core.symbol import Symbol


@pytest.fixture
def sym():
    with patch.object(Symbol, "_start_watching", lambda self: None):
        w = MagicMock()
        mgr = MagicMock()
        s = Symbol("my.mod:Cls.fn", w, mgr)
        try:
            yield s
        finally:
            s.stop()


def test_given_hook_not_applied_when_update_hook_then_returns_false(sym):
    assert sym.update_hook() is False


def test_given_applied_hook_and_no_handlers_when_update_hook_then_unhooks(sym):
    sym._hook_applied = True
    sym._hook_node = None
    assert sym.update_hook() is True
    assert sym._hook_applied is False


def test_given_locked_and_unlocked_handlers_when_remove_unlocked_then_only_unlocked_removed(sym):
    h1 = MagicMock()
    h1.lock_patch = False
    h2 = MagicMock()
    h2.lock_patch = True
    sym._handlers["u1"] = h1
    sym._handlers["l1"] = h2
    removed = sym.remove_unlocked_handlers()
    assert "u1" in removed
    assert "u1" not in sym._handlers
    assert "l1" in sym._handlers
    assert sym.has_locked_handlers() is True
    assert sym.has_handlers() is True


def test_given_sync_inner_and_two_wrappers_when_build_chain_then_applies_outer_to_inner(sym):
    def w1(ori, *a, **k):
        return ori(*a, **k) + 1

    def w2(ori, *a, **k):
        return ori(*a, **k) * 2

    inner = lambda: 10
    chain = sym._build_sync_wrap_chain(inner, [w1, w2])
    # 洋葱模型：wrap_funcs=[w1,w2] -> 实际执行为 w1(w2(inner))
    # inner=10 -> w2(inner)=20 -> w1(...)=21
    assert chain() == 21


def test_given_async_inner_and_wrap_when_build_chain_then_await_returns_value(sym):
    async def inner():
        return 3

    async def wrap(ori, *a, **k):
        return await ori(*a, **k)

    out = sym._build_wrap_chain(inner, inner, [wrap])
    assert asyncio.run(out()) == 3



def test_given_module_loaded_but_no_handlers_when_hook_then_short_circuits(sym):
    sym._module_loaded = True
    sym.hook()
    assert sym._hook_applied is False
    assert sym._hook_node is None


def test_given_already_hooked_unchanged_handlers_when_hook_then_short_circuits(sym):
    sym._module_loaded = True
    sym._handlers_changed = False
    sym._hook_applied = True
    sym._hook_node = MagicMock()
    # 至少要存在 handlers，才能走到 “已经 hooked 且无变化 -> short-circuit” 的分支
    sym._handlers["h"] = MagicMock()
    old_node = sym._hook_node
    sym.hook()
    assert sym._hook_applied is True
    assert sym._handlers_changed is False
    assert sym._hook_node is old_node


def test_given_module_path_not_found_when_import_target_then_returns_none(sym):
    sym._module_path = "nonexistent.module.path"
    sym._attr_path = "SomeClass.method"
    assert sym._import_target() is None


def test_given_attribute_path_not_found_when_import_target_then_returns_none(sym):
    sym._module_path = "os"
    sym._attr_path = "NonexistentClass.method"
    assert sym._import_target() is None


def test_given_async_inner_and_two_wrappers_when_build_async_wrap_chain_then_await_returns_value(sym):
    async def inner():
        return 10

    async def w1(ori, *a, **k):
        return (await ori(*a, **k)) + 1

    async def w2(ori, *a, **k):
        return (await ori(*a, **k)) * 2

    out = sym._build_async_wrap_chain(inner, [w1, w2])
    assert asyncio.run(out()) == 21
