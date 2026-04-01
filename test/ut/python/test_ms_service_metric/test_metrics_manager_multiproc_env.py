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

"""MetricsManager registry selection when PROMETHEUS_MULTIPROC_DIR is set."""

import tempfile

import pytest
from prometheus_client import REGISTRY

pytest.importorskip("ms_service_metric.metrics.metrics_manager")

from ms_service_metric.metrics.metrics_manager import MetricConfig, MetricType, MetricsManager


def test_given_multiproc_dir_env_when_register_then_uses_collector_registry_not_default(
    monkeypatch,
):
    # TemporaryDirectory removes the tree on exit; avoids fixed /tmp paths and
    # leftover multiprocess files when the suite is run repeatedly.
    with tempfile.TemporaryDirectory(prefix="ms_metric_ut_multiproc_") as multiproc_dir:
        monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", multiproc_dir)
        mgr = MetricsManager()
        mgr.register_metric(MetricConfig(name="ut_counter", type=MetricType.COUNTER))
        reg = mgr.get_registry()
        assert reg is not None
        assert reg is not REGISTRY
        from prometheus_client import CollectorRegistry

        assert isinstance(reg, CollectorRegistry)
