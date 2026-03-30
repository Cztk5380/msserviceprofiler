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

"""SymbolHandlerManager.initialize / shutdown integration (heavy deps mocked)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def shm_prefix(monkeypatch):
    p = f"/ut_sym_init_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MS_SERVICE_METRIC_SHM_PREFIX", p)
    monkeypatch.setenv("MS_SERVICE_METRIC_MAX_PROCS", "8")
    return p


def test_given_empty_yaml_config_when_initialize_and_shutdown_then_start_stop_called(tmp_path, shm_prefix):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    cfg = tmp_path / "empty.yaml"
    cfg.write_text("[]\n")
    m = SymbolHandlerManager()
    with (
        patch.object(m._control_watch, "start", MagicMock()),
        patch.object(m._control_watch, "stop", MagicMock()),
        patch.object(m._watcher, "start", MagicMock()),
        patch.object(m._watcher, "stop", MagicMock()),
    ):
        m.initialize(str(cfg))
        m.shutdown()


def test_given_symbols_registered_when_apply_all_hooks_then_hook_called_each(shm_prefix):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    with patch("ms_service_metric.core.symbol_handler_manager.Symbol") as mock_sym_cls:
        sym = MagicMock()
        sym.hook_applied = True
        mock_sym_cls.return_value = sym
        m = SymbolHandlerManager()
        m._symbols["x:y"] = sym
        m._apply_all_hooks()
        sym.hook.assert_called_once()
