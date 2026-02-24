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

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from ms_service_profiler.patcher.core import metric_hook
from ms_service_profiler.patcher.core.metric_hook import (
    MetricConfig,
    MetricType,
    HookMetrics,
    TIMER_BUCKETS,
    parse_metrics_config,
    wrap_handler_with_metrics,
    get_hook_metrics,
)

# 用于 record_metric 测试的桩类型
class _StubHistogram:
    pass


class _StubCounter:
    pass


class _StubGauge:
    pass


class _StubSummary:
    pass


def _patch_all_metric_types():
    """同时 patch 四个指标类型，避免未 patch 的类型在 isinstance 中触发 TypeError"""
    return patch.multiple(
        "ms_service_profiler.patcher.core.metric_hook",
        Histogram=_StubHistogram,
        Counter=_StubCounter,
        Gauge=_StubGauge,
        Summary=_StubSummary,
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

    def test_sanitize_metric_name_keeps_valid_name(self):
        """指标名以字母开头时保持不变（仅替换连字符）"""
        client = HookMetrics()
        assert client._sanitize_metric_name("valid_metric") == "valid_metric"

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

    def test_add_dp_label_name_with_none(self):
        client = HookMetrics()
        assert "dp" in client._add_dp_label_name(None)

    def test_add_dp_label_value_preserves_existing_dp(self):
        """labels 中已有 dp 时直接返回"""
        client = HookMetrics()
        labels = {"dp": "0", "other": "x"}
        result = client._add_dp_label_value(labels)
        assert result == labels

    def test_add_dp_label_value_adds_dp_when_meta_state_ok(self):
        """meta_state 有 dp_rank_id 时使用其值"""
        client = HookMetrics()
        meta = MagicMock()
        meta.dp_rank_id = 3
        client.meta_state = meta
        result = client._add_dp_label_value({})
        assert result["dp"] == "3"

    def test_add_dp_label_value_adds_minus_one_when_meta_state_fails(self):
        """meta_state 为 None 或异常时使用 -1"""
        client = HookMetrics()
        client.meta_state = None
        result = client._add_dp_label_value({})
        assert result["dp"] == "-1"

    def test_add_dp_label_value_with_none_labels(self):
        client = HookMetrics()
        client.meta_state = None
        result = client._add_dp_label_value(None)
        assert result["dp"] == "-1"

    def test_get_appropriate_registry_single_process(self):
        """单进程环境返回 REGISTRY"""
        with patch.dict(os.environ, {}, clear=True):
            registry = HookMetrics._get_appropriate_registry()
            from prometheus_client import REGISTRY
            assert registry is REGISTRY

    def test_get_appropriate_registry_multiprocess(self):
        """多进程环境创建 CollectorRegistry"""
        with patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": "/tmp/prom"}, clear=False):
            with patch("ms_service_profiler.patcher.core.metric_hook.multiprocess.MultiProcessCollector") as mock_mp:
                registry = HookMetrics._get_appropriate_registry()
                assert registry is not None
                mock_mp.assert_called_once()

    def test_generate_custom_buckets(self):
        """_generate_custom_buckets 返回排序后的分桶列表"""
        client = HookMetrics()
        buckets = client._generate_custom_buckets()
        assert isinstance(buckets, list)
        assert buckets == sorted(buckets)
        assert float('inf') in buckets
        assert 262144 in buckets

    def test_register_metric_creates_histogram(self):
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="test_hist", type=MetricType.HISTOGRAM, buckets=[1.0, 2.0])
        with patch("ms_service_profiler.patcher.core.metric_hook.Histogram") as MockHist:
            MockHist.return_value = MagicMock()
            client.register_metric(cfg, ["dp"])
            assert "test_hist" in client.metrics or any("test_hist" in k for k in client.metrics.keys())

    def test_register_metric_creates_timer(self):
        """TIMER 类型使用 Histogram 实现"""
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="test_timer", type=MetricType.TIMER)
        with patch("ms_service_profiler.patcher.core.metric_hook.Histogram") as MockHist:
            MockHist.return_value = MagicMock()
            client.register_metric(cfg)
            MockHist.assert_called_once()
            call_kw = MockHist.call_args[1]
            assert call_kw["buckets"] == TIMER_BUCKETS

    def test_register_metric_creates_counter(self):
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="test_counter", type=MetricType.COUNTER)
        with patch("ms_service_profiler.patcher.core.metric_hook.Counter") as MockCounter:
            MockCounter.return_value = MagicMock()
            client.register_metric(cfg)
            MockCounter.assert_called_once()

    def test_register_metric_creates_gauge(self):
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="test_gauge", type=MetricType.GAUGE)
        with patch("ms_service_profiler.patcher.core.metric_hook.Gauge") as MockGauge:
            MockGauge.return_value = MagicMock()
            client.register_metric(cfg)
            MockGauge.assert_called_once()

    def test_register_metric_creates_summary(self):
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="test_summary", type=MetricType.SUMMARY)
        with patch("ms_service_profiler.patcher.core.metric_hook.Summary") as MockSummary:
            MockSummary.return_value = MagicMock()
            client.register_metric(cfg)
            MockSummary.assert_called_once()

    def test_register_metric_histogram_uses_custom_buckets(self):
        """HISTOGRAM 无 buckets 时使用 _generate_custom_buckets"""
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="h1", type=MetricType.HISTOGRAM)
        with patch.object(client, "_generate_custom_buckets", return_value=[0, 1, 2]) as mock_gen:
            with patch("ms_service_profiler.patcher.core.metric_hook.Histogram") as MockHist:
                MockHist.return_value = MagicMock()
                client.register_metric(cfg)
                mock_gen.assert_called_once()
                assert MockHist.call_args[1]["buckets"] == [0, 1, 2]

    def test_register_metric_init_registry_when_none(self):
        """registry 为 None 时自动初始化"""
        client = HookMetrics()
        client.registry = None
        with patch.object(HookMetrics, "_get_appropriate_registry", return_value=MagicMock()) as mock_get:
            with patch("ms_service_profiler.patcher.core.metric_hook.Histogram") as MockHist:
                MockHist.return_value = MagicMock()
                cfg = MetricConfig(name="t1", type=MetricType.TIMER)
                client.register_metric(cfg)
                mock_get.assert_called_once()

    def test_register_metric_value_error_uses_cached(self):
        """ValueError 时若已缓存则使用缓存实例"""
        client = HookMetrics()
        client.registry = MagicMock()
        cached = MagicMock()
        client.metrics["test_metric"] = cached
        cfg = MetricConfig(name="test_metric", type=MetricType.TIMER)
        with patch("ms_service_profiler.patcher.core.metric_hook.Histogram") as MockHist:
            MockHist.side_effect = ValueError("duplicate")
            result = client.register_metric(cfg)
            assert result is cached

    def test_register_metric_value_error_logs_when_not_cached(self):
        """ValueError 且未缓存时打 warning"""
        client = HookMetrics()
        client.registry = MagicMock()
        cfg = MetricConfig(name="new_metric", type=MetricType.TIMER)
        with patch("ms_service_profiler.patcher.core.metric_hook.Histogram") as MockHist:
            MockHist.side_effect = ValueError("duplicate")
            with patch("ms_service_profiler.patcher.core.metric_hook.logger") as mock_logger:
                result = client.register_metric(cfg)
                mock_logger.warning.assert_called()
                assert "Failed to create metric" in str(mock_logger.warning.call_args)

    def test_add_label_definition(self):
        client = HookMetrics()
        client.add_label_definition("m1", "label1", "args[0]")
        assert "m1" in client.label_definitions
        assert len(client.label_definitions["m1"]) == 1
        assert client.label_definitions["m1"][0]["name"] == "label1"
        assert client.label_definitions["m1"][0]["expr"] == "args[0]"
        client.add_label_definition("m1", "label2", "ret")
        assert len(client.label_definitions["m1"]) == 2

    def test_get_labels_for_metric(self):
        client = HookMetrics()
        client.add_label_definition("m1", "l1", "args[0]")
        with patch("ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr", return_value="val1"):
            labels = client.get_labels_for_metric("m1", {"args": ("val1",), "func_obj": None, "this": None, "kwargs": {}, "return": None})
            assert labels == {"l1": "val1"}

    def test_get_labels_for_metric_empty_expr_skipped(self):
        client = HookMetrics()
        client.add_label_definition("m1", "l1", "")
        labels = client.get_labels_for_metric("m1", {})
        assert labels == {}

    def test_get_labels_for_metric_eval_returns_none_skipped(self):
        client = HookMetrics()
        client.add_label_definition("m1", "l1", "args[0]")
        with patch("ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr", return_value=None):
            labels = client.get_labels_for_metric("m1", {"args": ()})
            assert labels == {}

    def test_get_registry(self):
        client = HookMetrics()
        client.registry = MagicMock()
        assert client.get_registry() is client.registry

    def test_get_all_metrics(self):
        client = HookMetrics()
        client.metrics = {"a": 1, "b": 2}
        assert client.get_all_metrics() == {"a": 1, "b": 2}

    def test_record_metric_histogram_with_labels(self):
        """使用桩类型替换全部指标类型，使 isinstance 通过"""
        mock_hist = MagicMock()
        mock_hist.__class__ = _StubHistogram
        with _patch_all_metric_types():
            client = HookMetrics()
            client.metrics["m1"] = mock_hist
            client.record_metric("m1", 0.5, {"dp": "0"})
        mock_hist.labels.assert_called_once_with(dp="0")
        mock_hist.labels.return_value.observe.assert_called_once_with(0.5)

    def test_record_metric_histogram_without_labels(self):
        mock_hist = MagicMock()
        mock_hist.__class__ = _StubHistogram
        with _patch_all_metric_types():
            client = HookMetrics()
            client.metrics["m1"] = mock_hist
            with patch.object(client, "_add_dp_label_value", return_value={}):
                client.record_metric("m1", 0.5, None)
        mock_hist.observe.assert_called_once_with(0.5)

    def test_record_metric_counter_with_labels(self):
        mock_counter = MagicMock()
        mock_counter.__class__ = _StubCounter
        with _patch_all_metric_types():
            client = HookMetrics()
            client.metrics["m1"] = mock_counter
            client.record_metric("m1", 0, {"dp": "0"})
        mock_counter.labels.assert_called_once_with(dp="0")
        mock_counter.labels.return_value.inc.assert_called_once_with(1)

    def test_record_metric_counter_positive_value(self):
        mock_counter = MagicMock()
        mock_counter.__class__ = _StubCounter
        with _patch_all_metric_types():
            client = HookMetrics()
            client.metrics["m1"] = mock_counter
            with patch.object(client, "_add_dp_label_value", return_value={}):
                client.record_metric("m1", 5, None)
        mock_counter.inc.assert_called_once_with(5)

    def test_record_metric_gauge(self):
        mock_gauge = MagicMock()
        mock_gauge.__class__ = _StubGauge
        with _patch_all_metric_types():
            client = HookMetrics()
            client.metrics["m1"] = mock_gauge
            with patch.object(client, "_add_dp_label_value", return_value={}):
                client.record_metric("m1", 100, None)
        mock_gauge.set.assert_called_once_with(100)

    def test_record_metric_summary(self):
        mock_summary = MagicMock()
        mock_summary.__class__ = _StubSummary
        with _patch_all_metric_types():
            client = HookMetrics()
            client.metrics["m1"] = mock_summary
            with patch.object(client, "_add_dp_label_value", return_value={}):
                client.record_metric("m1", 1.5, None)
        mock_summary.observe.assert_called_once_with(1.5)

    def test_record_metric_exception_logs_warning(self):
        mock_metric = MagicMock()
        mock_metric.__class__ = _StubHistogram
        mock_metric.observe.side_effect = RuntimeError("test")
        with _patch_all_metric_types():
            client = HookMetrics()
            client.metrics["m1"] = mock_metric
            with patch.object(client, "_add_dp_label_value", return_value={}):
                with patch("ms_service_profiler.patcher.core.metric_hook.logger") as mock_logger:
                    client.record_metric("m1", 1.0, None)
                    mock_logger.warning.assert_called()

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

    def test_parse_metrics_config_skips_non_dict_items(self):
        """非 dict 的 item 被跳过"""
        metrics, _ = parse_metrics_config([{"name": "ok", "type": "timer"}, "invalid", 123])
        assert len(metrics) == 1

    def test_parse_metrics_config_skips_non_list(self):
        metrics, labels = parse_metrics_config("not a list")
        assert metrics == [] and labels == []

    def test_parse_metrics_config_dict_without_metrics_returns_empty(self):
        metrics, labels = parse_metrics_config({"other": "key"})
        assert metrics == [] and labels == []

    def test_parse_metrics_config_label_skips_invalid(self):
        """label 非 dict 或缺少 name/expr 时跳过"""
        _, labels = parse_metrics_config([
            {"name": "m1", "type": "counter", "label": [
                {"name": "l1", "expr": "x"},
                {"name": "", "expr": "y"},
                {"expr": "z"},
                "not_dict",
            ]}
        ])
        assert len(labels) == 1
        assert labels[0]["label_name"] == "l1"


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

    def test_wrap_handler_with_timer_metrics_records_duration(self):
        """带 timer 指标的 handler 会记录耗时"""
        def inner(orig, *args, **kwargs):
            return orig(*args, **kwargs)

        symbol_info = {
            "metrics": [{"name": "test:duration", "type": "timer"}]
        }
        with patch("ms_service_profiler.patcher.core.metric_hook.get_hook_metrics") as mock_get:
            mock_client = MagicMock()
            mock_client.metrics = {"test_duration": MagicMock()}
            mock_client.get_labels_for_metric.return_value = {}
            mock_client.register_metric.return_value = MagicMock()
            mock_get.return_value = mock_client
            wrapped = wrap_handler_with_metrics(inner, symbol_info)
            orig = MagicMock(return_value=99)
            result = wrapped(orig, 1, 2)
            assert result == 99
            mock_client.record_metric.assert_called_once()
            assert mock_client.record_metric.call_args[0][0] == "test:duration"

    def test_wrap_handler_with_expr_metric_records_value(self):
        """带 expr 的非 timer 指标会计算并记录"""
        def inner(orig, *args, **kwargs):
            return orig(*args, **kwargs)

        symbol_info = {
            "metrics": [{"name": "ret_count", "type": "counter", "expr": "ret"}]
        }
        with patch("ms_service_profiler.patcher.core.metric_hook.get_hook_metrics") as mock_get:
            mock_client = MagicMock()
            mock_client.metrics = {"ret_count": MagicMock()}
            mock_client.get_labels_for_metric.return_value = {}
            mock_client.register_metric.return_value = MagicMock()
            mock_get.return_value = mock_client
            with patch("ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr", return_value=10):
                wrapped = wrap_handler_with_metrics(inner, symbol_info)
                orig = MagicMock(return_value=10)
                result = wrapped(orig)
                assert result == 10
                mock_client.record_metric.assert_called_once_with("ret_count", 10.0, {})

    def test_wrap_handler_expr_eval_none_skips_record(self):
        """expr 评估为 None 时不记录"""
        def inner(orig, *args, **kwargs):
            return orig(*args, **kwargs)

        symbol_info = {"metrics": [{"name": "m1", "type": "counter", "expr": "bad_expr"}]}
        with patch("ms_service_profiler.patcher.core.metric_hook.get_hook_metrics") as mock_get:
            mock_client = MagicMock()
            mock_client.metrics = {"m1": MagicMock()}
            mock_client.get_labels_for_metric.return_value = {}
            mock_client.register_metric.return_value = MagicMock()
            mock_get.return_value = mock_client
            with patch("ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr", return_value=None):
                wrapped = wrap_handler_with_metrics(inner, symbol_info)
                wrapped(MagicMock(return_value=1))
                mock_client.record_metric.assert_not_called()

    def test_wrap_handler_expr_non_numeric_logs_debug(self):
        """expr 结果无法转为 float 时打 debug"""
        def inner(orig, *args, **kwargs):
            return orig(*args, **kwargs)

        symbol_info = {"metrics": [{"name": "m1", "type": "counter", "expr": "ret"}]}
        with patch("ms_service_profiler.patcher.core.metric_hook.get_hook_metrics") as mock_get:
            mock_client = MagicMock()
            mock_client.metrics = {"m1": MagicMock()}
            mock_client.get_labels_for_metric.return_value = {}
            mock_client.register_metric.return_value = MagicMock()
            mock_get.return_value = mock_client
            with patch("ms_service_profiler.patcher.core.dynamic_hook._safe_eval_expr", return_value="not_a_number"):
                with patch("ms_service_profiler.patcher.core.metric_hook.logger") as mock_logger:
                    wrapped = wrap_handler_with_metrics(inner, symbol_info)
                    wrapped(MagicMock(return_value=1))
                    mock_logger.debug.assert_called()

    def test_wrap_handler_async_invokes_and_records(self):
        """异步 handler 正确执行并记录"""
        async def inner(orig, *args, **kwargs):
            return await orig(*args, **kwargs)

        async def orig(*a, **k):
            return 123

        symbol_info = {"metrics": [{"name": "t1", "type": "timer"}]}
        with patch("ms_service_profiler.patcher.core.metric_hook.get_hook_metrics") as mock_get:
            mock_client = MagicMock()
            mock_client.metrics = {"t1": MagicMock()}
            mock_client.get_labels_for_metric.return_value = {}
            mock_client.register_metric.return_value = MagicMock()
            mock_get.return_value = mock_client
            wrapped = wrap_handler_with_metrics(inner, symbol_info)
            result = asyncio.run(wrapped(orig, 1, 2))
            assert result == 123
            mock_client.record_metric.assert_called_once()
