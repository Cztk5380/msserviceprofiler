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

"""MetricControlWatch behavior without starting SIGUSR1 / full lifecycle."""

import uuid
from unittest.mock import MagicMock

import pytest

from ms_service_metric.core.config.metric_control_watch import MetricControlWatch


@pytest.fixture
def unique_shm_prefix(monkeypatch):
    prefix = f"/ut_mcw_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MS_SERVICE_METRIC_SHM_PREFIX", prefix)
    monkeypatch.setenv("MS_SERVICE_METRIC_MAX_PROCS", "8")
    return prefix


def test_register_callback_fires_immediately_when_already_on(unique_shm_prefix):
    w = MetricControlWatch()
    w._current_state = w.STATE_ON
    w._last_timestamp = 11
    cb = MagicMock()
    w.register_callback(cb)
    cb.assert_called_once_with(True, 11)


def test_unregister_callback(unique_shm_prefix):
    w = MetricControlWatch()
    cb = MagicMock()
    w.register_callback(cb)
    w.unregister_callback(cb)
    w.unregister_callback(cb)  # idempotent
    assert len(w._callbacks) == 0


def test_get_last_timestamp_and_is_enabled(unique_shm_prefix):
    w = MetricControlWatch()
    w._last_timestamp = 5
    w._current_state = w.STATE_OFF
    assert w.get_last_timestamp() == 5
    assert w.is_enabled() is False
    w._current_state = w.STATE_ON
    assert w.is_enabled() is True
