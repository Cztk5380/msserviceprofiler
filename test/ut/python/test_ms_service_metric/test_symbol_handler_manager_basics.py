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

from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager


def test_given_new_manager_when_inspect_defaults_then_disabled_empty_stats():
    """测试 SymbolHandlerManager 默认状态与空 stats。"""
    m = SymbolHandlerManager()
    assert m.is_enabled() is False
    assert m.is_updating() is False
    stats = m.get_stats()
    assert stats["enabled"] is False
    assert stats["updating"] is False
    assert stats["symbol_count"] == 0
    assert stats["handler_count"] == 0
    assert stats["hooked_symbols"] == 0
    assert m.get_symbol("nonexistent:path") is None
    assert m.get_handler("no-such-id") is None
    assert not m.get_all_symbols()
    assert not m.get_all_handlers()


def test_given_same_handler_for_different_symbols_when_update_then_keeps_each_symbol():
    m = SymbolHandlerManager()
    handler_config = {"handler": "ms_service_metric.handlers:default_handler"}
    config = {
        "module:func1": [handler_config],
        "module:func2": [handler_config],
    }

    m._update_handlers(config)

    assert set(m.get_all_symbols()) == {"module:func1", "module:func2"}
    assert len(m.get_all_handlers()) == 2
