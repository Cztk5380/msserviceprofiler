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

from unittest.mock import MagicMock, patch

import pytest

from ms_service_profiler.patcher.vllm.metrics.definitions import (
    MetricConstants,
    BucketConfig,
    MetricManager,
)


class TestMetricConstants:
    """测试 MetricConstants 常量"""

    def test_total_tokens(self):
        assert MetricConstants.TOTAL_TOKENS == "total_tokens"

    def test_batch_size(self):
        assert MetricConstants.BATCH_SIZE == "batch_size"

    def test_second_token_latency(self):
        assert MetricConstants.SECOND_TOKEN_LATENCY == "second_token_latency"

    def test_kvcache_constants(self):
        assert MetricConstants.TOTAL_KVCACHE_BLOCKS == "total_kvcache_blocks"
        assert MetricConstants.FREE_KVCACHE_BLOCKS == "free_kvcache_blocks"
        assert MetricConstants.ALLOCATED_KVCACHE_BLOCKS == "allocated_kvcache_blocks"


class TestBucketConfig:
    """测试 BucketConfig 桶配置"""

    def test_custom_buckets_non_empty(self):
        assert len(BucketConfig.CUSTOM_BUCKETS) > 0
        assert BucketConfig.CUSTOM_BUCKETS[-1] == float("inf")

    def test_second_token_buckets_positive(self):
        for b in BucketConfig.SECOND_TOKEN_BUCKETS:
            assert b >= 0

    def test_total_tokens_buckets_powers_of_two_like(self):
        assert 1 in BucketConfig.TOTAL_TOKENS_BUCKETS
        assert 1024 in BucketConfig.TOTAL_TOKENS_BUCKETS


class TestMetricManager:
    """测试 MetricManager 类"""

    def test_metric_configs_contains_expected_keys(self):
        assert MetricConstants.BATCH_SIZE in MetricManager.METRIC_CONFIGS
        assert MetricConstants.TOTAL_TOKENS in MetricManager.METRIC_CONFIGS
        assert MetricConstants.SECOND_TOKEN_LATENCY in MetricManager.METRIC_CONFIGS
        assert MetricConstants.TOTAL_KVCACHE_BLOCKS in MetricManager.METRIC_CONFIGS

    def test_get_config_returns_config_for_known_metric(self):
        cfg = MetricManager.get_config(MetricConstants.BATCH_SIZE)
        assert cfg is not None
        assert cfg.name == MetricConstants.BATCH_SIZE

    def test_get_config_returns_none_for_unknown_metric(self):
        assert MetricManager.get_config("unknown_metric_name_xyz") is None

    def test_record_metric_unknown_metric_logs_warning(self):
        with patch.object(MetricManager, "metrics_client") as mock_client:
            mock_client.metrics = {}
            with patch("ms_service_profiler.patcher.vllm.metrics.definitions.logger") as mock_logger:
                MetricManager.record_metric("unknown_metric_xyz", {"dp": "0"}, 1.0)
                mock_logger.warning.assert_called_once()
                assert "unknown_metric_xyz" in mock_logger.warning.call_args[0][0] or "No configuration" in str(mock_logger.warning.call_args)

    def test_record_metric_registers_then_records_when_not_registered(self):
        with patch.object(MetricManager, "metrics_client") as mock_client:
            mock_client.metrics = {}
            with patch.object(MetricManager, "get_config") as mock_get_config:
                from ms_service_profiler.patcher.core.metric_hook import MetricConfig, MetricType
                mock_get_config.return_value = MetricConfig(name=MetricConstants.BATCH_SIZE, type=MetricType.HISTOGRAM, buckets=[1, 2])
                with patch("ms_service_profiler.patcher.vllm.metrics.definitions.logger"):
                    MetricManager.record_metric(MetricConstants.BATCH_SIZE, {"dp": "0"}, 5)
                    mock_client.register_metric.assert_called_once()
                    mock_client.record_metric.assert_called_once_with(
                        MetricConstants.BATCH_SIZE, 5, {"dp": "0"}
                    )

    def test_record_metric_skips_when_metric_already_registered(self):
        with patch.object(MetricManager, "metrics_client") as mock_client:
            mock_client.metrics = {MetricConstants.BATCH_SIZE: MagicMock()}
            MetricManager.record_metric(MetricConstants.BATCH_SIZE, {"dp": "0"}, 3)
            mock_client.record_metric.assert_called_once_with(
                MetricConstants.BATCH_SIZE, 3, {"dp": "0"}
            )
