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

"""MetricControlWatch failure paths and signal handler branches."""

import signal
import uuid
from unittest.mock import MagicMock, patch

import pytest

from ms_service_metric.core.config.metric_control_watch import MetricControlWatch
from ms_service_metric.utils.exceptions import SharedMemoryError


@pytest.fixture
def shm_prefix(monkeypatch):
    prefix = f"/ut_mcw_sig_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MS_SERVICE_METRIC_SHM_PREFIX", prefix)
    monkeypatch.setenv("MS_SERVICE_METRIC_MAX_PROCS", "8")
    return prefix


def test_register_callback_errors_swallowed(shm_prefix):
    """STATE_ON 下注册回调会立即执行；异常被吞并记 error 日志（mock logger，caplog 捕不到自定义 handler）。"""
    w = MetricControlWatch()
    w._current_state = w.STATE_ON

    def bad(_a, _b):
        raise RuntimeError("x")

    with patch("ms_service_metric.core.config.metric_control_watch.logger") as log_mock:
        w.register_callback(bad)

    assert bad in w._callbacks
    log_mock.error.assert_called_once()
    msg = log_mock.error.call_args[0][0]
    assert "Callback error during registration" in msg
    assert "x" in msg


def test_signal_handler_skips_when_lock_busy(shm_prefix):
    """acquire(blocking=False) 失败时不进入处理逻辑，不调用 release，不改变当前状态。"""
    w = MetricControlWatch()
    lock = MagicMock()
    lock.acquire = MagicMock(return_value=False)
    lock.release = MagicMock()
    w._signal_lock = lock
    original_state = w._current_state
    with patch.object(w, "_check_control_state") as ch, patch(
        "ms_service_metric.core.config.metric_control_watch.logger"
    ) as log_mock:
        w._signal_handler(signal.SIGUSR1, None)
    lock.acquire.assert_called_once_with(blocking=False)
    lock.release.assert_not_called()
    assert w._current_state == original_state
    ch.assert_not_called()
    log_mock.warning.assert_called_once()
    assert "Signal handler already running" in log_mock.warning.call_args[0][0]


def test_signal_handler_chains_original(shm_prefix):
    calls = []

    def orig(s, f):
        calls.append((s, f))

    w = MetricControlWatch()
    w._original_handler = orig
    with patch.object(w, "_check_control_state"):
        w._signal_handler(signal.SIGUSR1, None)
    assert calls


def test_signal_handler_ignores_other_signum(shm_prefix):
    w = MetricControlWatch()
    w._original_handler = None
    with patch.object(w, "_check_control_state") as ch:
        w._signal_handler(signal.SIGINT, None)
        ch.assert_not_called()


def test_start_failure_resets_running(shm_prefix):
    w = MetricControlWatch()
    with patch(
        "ms_service_metric.core.config.metric_control_watch.SharedMemoryManager"
    ) as m:
        m.return_value.connect.side_effect = RuntimeError("connect failed")
        with pytest.raises(RuntimeError):
            w.start()
        assert w._running is False


def test_stop_when_never_started(shm_prefix):
    w = MetricControlWatch()
    w.stop()


def test_set_control_state_failure_path(shm_prefix):
    mgr = MagicMock()
    mgr.connect.return_value = True
    mgr.send_control_command.return_value = (False, 0, 0, False)
    with patch(
        "ms_service_metric.core.config.metric_control_watch.SharedMemoryManager",
        return_value=mgr,
    ):
        with pytest.raises(SharedMemoryError, match="Failed to send"):
            MetricControlWatch.set_control_state(True, shm_prefix=shm_prefix)
