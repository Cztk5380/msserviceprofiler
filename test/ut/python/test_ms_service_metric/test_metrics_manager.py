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

import pytest

pytest.importorskip("ms_service_metric.metrics.metrics_manager")

from ms_service_metric.metrics.metrics_manager import MetricConfig, MetricType, MetricsManager


def test_given_metric_config_timer_when_constructed_then_expr_cleared_and_labels_default_dict():
    cfg = MetricConfig(name="t1", type=MetricType.TIMER, expr="should_be_cleared")
    assert cfg.expr == ""
    assert isinstance(cfg.labels, dict)


def test_given_registered_counter_when_recorded_then_increments_track_last_and_negative_maps_to_one():
    manager = MetricsManager()
    manager.metric_prefix = "vllm"

    config = MetricConfig(name="test_counter", type=MetricType.COUNTER)
    metric_obj = manager.register_metric(config)
    assert metric_obj is not None

    full_name = "vllm_test_counter"
    assert full_name in manager.get_all_metrics()

    manager.record_metric("test_counter", 3)
    assert metric_obj._last_inc == 3

    manager.record_metric("test_counter", -10)
    assert metric_obj._last_inc == 1


def test_given_prefixed_manager_when_register_timer_with_hyphen_and_record_then_name_sanitized_and_labels_merged():
    manager = MetricsManager()
    manager.metric_prefix = "p"

    cfg = MetricConfig(name="test-timer", type=MetricType.TIMER, labels=None)
    metric_obj = manager.register_metric(cfg)
    assert metric_obj is not None

    full_name = "p_test_timer"
    assert full_name in manager.get_all_metrics()

    manager.record_metric("test-timer", 0.123, labels={"status": "success"})
    assert metric_obj._last_observe == 0.123
    assert metric_obj._last_labels["status"] == "success"
    assert "dp" in metric_obj._last_labels
    assert "role" in metric_obj._last_labels


def test_given_label_definition_when_builtin_evaluates_then_resolves_expression():
    from ms_service_metric.handlers.builtin import _get_labels_for_metric

    manager = MetricsManager()
    manager.metric_prefix = "vllm"

    manager.add_label_definition("test_metric", "status", "ret['status']")
    defs = manager.get_label_definitions()
    labels = _get_labels_for_metric("vllm_test_metric", {"ret": {"status": "ok"}}, defs)
    assert labels["status"] == "ok"
