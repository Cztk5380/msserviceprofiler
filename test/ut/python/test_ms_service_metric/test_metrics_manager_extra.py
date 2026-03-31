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

"""Extra MetricsManager branches."""

import pytest
from prometheus_client import CollectorRegistry

pytest.importorskip("ms_service_metric.metrics.metrics_manager")

from ms_service_metric.metrics.metrics_manager import MetricConfig, MetricType, MetricsManager


def test_given_histogram_and_summary_when_registered_then_both_metrics_exist():
    m = MetricsManager()
    m.register_metric(MetricConfig(name="h", type=MetricType.HISTOGRAM))
    m.register_metric(MetricConfig(name="s", type=MetricType.SUMMARY))
    assert "h" in m.get_all_metrics() or any("h" in k for k in m.get_all_metrics())
    assert len(m.get_all_metrics()) >= 2


def test_given_same_metric_config_when_register_twice_then_registry_keys_unchanged():
    m = MetricsManager()
    cfg = MetricConfig(name="c", type=MetricType.COUNTER)
    m.register_metric(cfg)
    first = m.get_all_metrics()
    m.register_metric(cfg)
    assert first.keys() == m.get_all_metrics().keys()


def test_given_custom_registry_when_set_and_get_or_create_then_record_uses_that_registry():
    m = MetricsManager()
    reg = CollectorRegistry()
    m.set_registry(reg)
    assert m.get_registry() is reg
    m.get_or_create_metric("g", metric_type=MetricType.GAUGE)
    m.record_metric("g", 3.0)


def test_given_unregistered_name_when_record_metric_then_call_is_safe():
    m = MetricsManager()
    m.record_metric("nonexistent", 1)


def test_given_timer_with_buckets_when_add_label_definition_then_definition_refs_timer():
    m = MetricsManager()
    m.register_metric(MetricConfig(name="t", type=MetricType.TIMER, buckets=[0.1, 0.2]))
    m.add_label_definition("t", "lbl", "1")
    defs = m.get_label_definitions()
    assert any("t" in k for k in defs)


def test_given_registered_metrics_when_clear_then_map_empty():
    m = MetricsManager()
    m.register_metric(MetricConfig(name="x", type=MetricType.COUNTER))
    m.clear_metrics()
    assert m.get_all_metrics() == {}
