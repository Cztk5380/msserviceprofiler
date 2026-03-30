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

"""SymbolHandlerManager internal paths (Symbol mocked to stay lightweight)."""

from unittest.mock import MagicMock, patch

import pytest
import logging


class _ListLogHandler(logging.Handler):
    """Collect log records emitted to the attached logger."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def mock_symbol_cls():
    with patch("ms_service_metric.core.symbol_handler_manager.Symbol") as m:
        sym = MagicMock()
        sym.hook_applied = False
        sym.is_empty.return_value = False
        sym.stop_unlocked.return_value = ([], [])
        m.return_value = sym
        yield m, sym


def _simple_handler_cfg():
    return {"handler": "ms_service_metric.handlers:default_handler"}


def test_given_handlers_value_not_list_when_update_handlers_then_no_handlers(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    mock_symbol_cls  # registers patch
    logger = logging.getLogger("ms_service_metric.symbol_handler_manager")
    capture = _ListLogHandler()
    capture.setLevel(logging.WARNING)
    logger.addHandler(capture)
    try:
        m = SymbolHandlerManager()
        m._update_handlers({"sym:x": "not-a-list"})
    finally:
        logger.removeHandler(capture)

    assert len(m._handlers) == 0
    msgs = [r.getMessage() for r in capture.records]
    assert any("Invalid handlers config for sym:x: expected list" in msg for msg in msgs)


def test_given_handlers_list_not_dict_when_update_handlers_then_no_handlers(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    logger = logging.getLogger("ms_service_metric.symbol_handler_manager")
    capture = _ListLogHandler()
    capture.setLevel(logging.WARNING)
    logger.addHandler(capture)
    try:
        m = SymbolHandlerManager()
        m._update_handlers({"sym:x": ["not-a-dict"]})
    finally:
        logger.removeHandler(capture)

    assert len(m._handlers) == 0
    msgs = [r.getMessage() for r in capture.records]
    assert any("Invalid handler config: expected dict" in msg for msg in msgs)


def test_given_valid_then_empty_config_when_update_handlers_then_handlers_removed(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    _, sym = mock_symbol_cls
    sym.is_empty.return_value = True
    m = SymbolHandlerManager()
    path = "test.mod:fn"
    m._update_handlers({path: [_simple_handler_cfg()]})
    assert path in m._symbols
    assert len(m._handlers) == 1
    hid = next(iter(m._handlers.keys()))
    sym.add_handler.assert_called_once()
    sym.reset_mock()

    m._update_handlers({})
    assert len(m._handlers) == 0
    sym.remove_handler.assert_called_once()


def test_given_unknown_handler_id_when_remove_handler_then_noop(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    logger = logging.getLogger("ms_service_metric.symbol_handler_manager")
    capture = _ListLogHandler()
    capture.setLevel(logging.WARNING)
    logger.addHandler(capture)
    try:
        m = SymbolHandlerManager()
        m._remove_handler("nope")
    finally:
        logger.removeHandler(capture)

    msgs = [r.getMessage() for r in capture.records]
    assert any("Handler not found for removal: nope" in msg for msg in msgs)
    assert len(m._handlers) == 0


def test_given_handler_not_tracked_when_update_handler_then_noop(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager
    from ms_service_metric.core.handler import MetricHandler

    logger = logging.getLogger("ms_service_metric.symbol_handler_manager")
    capture = _ListLogHandler()
    capture.setLevel(logging.WARNING)
    logger.addHandler(capture)
    try:
        m = SymbolHandlerManager()
        h = MetricHandler.from_config(_simple_handler_cfg(), "a:b")
        m._update_handler(h)
    finally:
        logger.removeHandler(capture)

    assert len(m._handlers) == 0
    msgs = [r.getMessage() for r in capture.records]
    assert any("Handler not found for update" in msg for msg in msgs)


def test_given_manager_disabled_when_control_off_then_no_graceful_stop(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    m = SymbolHandlerManager()
    m._enabled = False
    cw = MagicMock()
    m._control_watch = cw
    with patch.object(m, "_stop_all_symbols_graceful") as gr:
        m._on_control_state_change(False, 1)
        gr.assert_not_called()


def test_given_manager_enabled_when_control_off_then_graceful_stop_and_disabled(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    m = SymbolHandlerManager()
    m._enabled = True
    m._control_watch = MagicMock()
    with patch.object(m, "_stop_all_symbols_graceful") as gr:
        m._on_control_state_change(False, 0)
        gr.assert_called_once()
    assert m._enabled is False


def test_given_same_timestamp_when_control_on_then_idempotent(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    m = SymbolHandlerManager()
    m._enabled = True
    cw = MagicMock()
    cw.get_last_timestamp.return_value = 7
    m._control_watch = cw
    with patch.object(m, "_config") as cfg:
        with patch.object(m, "_update_handlers") as upd:
            m._on_control_state_change(True, 7)
            cfg.reload.assert_not_called()
            upd.assert_not_called()


def test_given_manager_disabled_when_control_on_then_noop(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    m = SymbolHandlerManager()
    m._enabled = False
    m._control_watch = MagicMock()
    m._control_watch.get_last_timestamp.return_value = 0
    with patch.object(m._config, "reload", return_value={}) as rel:
        with patch.object(m, "_update_handlers") as upd:
            with patch.object(m, "_apply_all_hooks") as app:
                m._on_control_state_change(True, 5)
    rel.assert_called_once()
    upd.assert_called_once()
    app.assert_called_once()
    assert m._enabled is True
    assert m._updating is False


def test_given_timestamp_changes_when_control_on_then_restarts_symbols(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    m = SymbolHandlerManager()
    m._enabled = True
    cw = MagicMock()
    cw.get_last_timestamp.return_value = 1
    m._control_watch = cw
    with patch.object(m, "_stop_all_symbols_graceful") as gr:
        with patch.object(m._config, "reload", return_value={}):
            with patch.object(m, "_update_handlers"):
                with patch.object(m, "_apply_all_hooks"):
                    m._on_control_state_change(True, 99)
        gr.assert_called_once()
    assert m._enabled is True


def test_given_registered_symbols_when_stop_all_then_each_stopped_handlers_cleared(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    _, sym = mock_symbol_cls
    m = SymbolHandlerManager()
    m._symbols["a:b"] = sym
    m._stop_all_symbols()
    sym.stop.assert_called_once()


def test_given_symbol_empty_after_stop_when_graceful_stop_then_symbol_removed(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    _, sym = mock_symbol_cls
    sym.stop_unlocked.return_value = (["h1"], [])
    m = SymbolHandlerManager()
    m._handlers["h1"] = MagicMock()
    m._symbols["p:q"] = sym
    m._stop_all_symbols_graceful()
    assert "p:q" not in m._symbols
    assert "h1" not in m._handlers


def test_given_locked_handlers_when_graceful_stop_then_symbol_retained(mock_symbol_cls):
    from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

    _, sym = mock_symbol_cls
    sym.stop_unlocked.return_value = (["h1"], ["h2"])
    m = SymbolHandlerManager()
    m._handlers["h2"] = MagicMock()
    m._symbols["p:q"] = sym
    m._stop_all_symbols_graceful()
    assert "p:q" in m._symbols
    sym.stop_watching.assert_not_called()
