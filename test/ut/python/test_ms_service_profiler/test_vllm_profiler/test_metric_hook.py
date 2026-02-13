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

import os
from unittest.mock import MagicMock, patch

import pytest

from ms_service_profiler.patcher.core.metric_hook import (
    MetricConfig,
    MetricType,
    HookMetrics,
    TIMER_BUCKETS,
    parse_metrics_config,
    wrap_handler_with_metrics,
    get_hook_metrics,
)


class TestMetricType:
    """测试 MetricType 枚举"""

    @pytest.mark.parametrize("name,expected", [
        ("timer", MetricType.TIMER),
        ("histogram", MetricType.HISTOGRAM),
        ("counter", MetricType.COUNTER),
        ("gauge", MetricType.GAUGE),
        ("summary", MetricType.SUMMARY),
    ])
    def test_metric_type_values(self, name, expected):
        assert MetricType(name) == expected

    def test_metric_type_invalid_raises(self):
        with pytest.raises(ValueError):
            MetricType("invalid_type")


class TestMetricConfig:
    """测试 MetricConfig 数据类"""

    def test_metric_config_timer_clears_expr(self):
        cfg = MetricConfig(name="t1", type=MetricType.TIMER, expr="x")
        assert cfg.expr == ""

    def test_metric_config_histogram_keeps_buckets(self):
        buckets = [0.1, 0.5, 1.0]
        cfg = MetricConfig(name="h1", type=MetricType.HISTOGRAM, buckets=buckets)
        assert cfg.buckets == buckets

    def test_metric_config_defaults(self):
        cfg = MetricConfig(name="c1", type=MetricType.COUNTER)
        assert cfg.expr == ""
        assert cfg.buckets is None


class TestHookMetrics:
    """测试 HookMetrics 类"""

    def test_sanitize_metric_name_replaces_hyphen(self):
        client = HookMetrics()
        assert client._sanitize_metric_name("my-metric") == "my_metric"

    def test_sanitize_metric_name_prefixes_digit(self):
        client = HookMetrics()
        assert client._sanitize_metric_name("123metric").startswith("fn_")

    def test_add_prefix_empty(self):
        client = HookMetrics()
        client.metric_prefix = ""
        assert client._add_prefix("name") == "name"

    def test_add_prefix_non_empty(self):
        client = HookMetrics()
        client.metric_prefix = "vllm"
        assert client._add_prefix("latency") == "vllm_latency"

    def test_add_dp_label_name_adds_dp(self):
        client = HookMetrics()
        assert "dp" in client._add_dp_label_name([])
        assert client._add_dp_label_name(["a"]) == ["a", "dp"]

    def test_add_dp_label_name_preserves_existing_dp(self):
        client = HookMetrics()
        result = client._add_dp_label_name(["dp", "x"])
        assert "dp" in result and "x" in result

    def test_register_metric_creates_histogram(self):
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="test_hist", type=MetricType.HISTOGRAM, buckets=[1.0, 2.0])
        with patch("ms_service_profiler.patcher.core.metric_hook.Histogram") as MockHist:
            MockHist.return_value = MagicMock()
            client.register_metric(cfg, ["dp"])
            assert "test_hist" in client.metrics or any("test_hist" in k for k in client.metrics.keys())

    def test_record_metric_unknown_logs_warning(self):
        client = HookMetrics()
        client.metrics = {}
        with patch("ms_service_profiler.patcher.core.metric_hook.logger") as mock_logger:
            client.record_metric("unknown_metric", 1.0, {"dp": "0"})
            mock_logger.warning.assert_called()


class TestGetHookMetrics:
    """测试 get_hook_metrics 单例"""

    def test_get_hook_metrics_returns_hook_metrics_instance(self):
        with patch("ms_service_profiler.patcher.core.metric_hook._hook_metrics_instance", None):
            import ms_service_profiler.patcher.core.metric_hook as m
            m._hook_metrics_instance = None
            inst = get_hook_metrics()
            assert isinstance(inst, HookMetrics)
            assert get_hook_metrics() is inst


class TestParseMetricsConfig:
    """测试 parse_metrics_config 函数"""

    def test_parse_metrics_config_none(self):
        metrics, labels = parse_metrics_config(None)
        assert metrics == []
        assert labels == []

    def test_parse_metrics_config_dict_uses_metrics_key(self):
        metrics, labels = parse_metrics_config({
            "metrics": [
                {"name": "m1", "type": "timer"},
            ]
        })
        assert len(metrics) == 1
        assert metrics[0].name == "m1"
        assert metrics[0].type == MetricType.TIMER

    def test_parse_metrics_config_list_direct(self):
        metrics, labels = parse_metrics_config([
            {"name": "counter1", "type": "counter", "expr": "ret"},
            {"name": "h1", "type": "histogram", "buckets": [0.1, 1.0]},
        ])
        assert len(metrics) == 2
        assert metrics[0].name == "counter1" and metrics[0].type == MetricType.COUNTER
        assert metrics[1].name == "h1" and metrics[1].buckets == [0.1, 1.0]

    def test_parse_metrics_config_skips_missing_name(self):
        with patch("ms_service_profiler.patcher.core.metric_hook.logger") as mock_logger:
            metrics, _ = parse_metrics_config([{"type": "timer"}, {"name": "ok", "type": "gauge"}])
            assert len(metrics) == 1
            assert metrics[0].name == "ok"

    def test_parse_metrics_config_skips_invalid_type(self):
        with patch("ms_service_profiler.patcher.core.metric_hook.logger"):
            metrics, _ = parse_metrics_config([{"name": "x", "type": "invalid"}])
            assert len(metrics) == 0

    def test_parse_metrics_config_collects_labels(self):
        _, labels = parse_metrics_config([
            {
                "name": "m1",
                "type": "counter",
                "label": [
                    {"name": "l1", "expr": "args[0]"},
                    {"name": "l2", "expr": "kwargs.get('x')"},
                ],
            }
        ])
        assert len(labels) == 2
        assert labels[0]["metric_name"] == "m1" and labels[0]["label_name"] == "l1"
        assert labels[1]["label_name"] == "l2"


class TestWrapHandlerWithMetrics:
    """测试 wrap_handler_with_metrics"""

    def test_wrap_handler_with_metrics_returns_callable(self):
        def dummy_handler(orig, *args, **kwargs):
            return orig(*args, **kwargs)

        wrapped = wrap_handler_with_metrics(dummy_handler, {"metrics": []})
        assert callable(wrapped)

    def test_wrap_handler_with_metrics_invokes_original(self):
        inner = MagicMock(return_value=42)
        symbol_info = {"metrics": []}
        with patch("ms_service_profiler.patcher.core.metric_hook.get_hook_metrics") as mock_get:
            mock_client = MagicMock()
            mock_client.metrics = {}
            mock_get.return_value = mock_client
            wrapped = wrap_handler_with_metrics(inner, symbol_info)
            orig = MagicMock()
            result = wrapped(orig, 1, 2, key="v")
            inner.assert_called_once()
            assert result == 42
