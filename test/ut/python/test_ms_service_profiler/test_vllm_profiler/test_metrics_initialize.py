# -------------------------------------------------------------------------
# Unit tests for ms_service_profiler.patcher.vllm.metrics.initialize
# -------------------------------------------------------------------------

import os
from unittest.mock import MagicMock, patch

import pytest

from ms_service_profiler.patcher.vllm.metrics import initialize


class TestSetVllmMultiprocessPrometheus:
    """测试 set_vllm_multiprocess_prometheus"""

    def test_when_vllm_metrics_available_and_no_env_logs_warning(self):
        with patch.object(initialize, "VLLM_METRICS_AVAILABLE", True):
            with patch.dict(os.environ, {}, clear=True):
                with patch("ms_service_profiler.patcher.vllm.metrics.initialize.logger") as mock_logger:
                    initialize.set_vllm_multiprocess_prometheus()
                    warning_calls = [c for c in mock_logger.warning.call_args_list if "PROMETHEUS_MULTIPROC_DIR" in str(c)]
                    assert len(warning_calls) >= 1

    def test_when_vllm_metrics_not_available_does_not_raise(self):
        with patch.object(initialize, "VLLM_METRICS_AVAILABLE", False):
            initialize.set_vllm_multiprocess_prometheus()


class TestSetVllmRegistry:
    """测试 set_vllm_registry（vllm 未安装时模块内无 get_prometheus_registry，用 __dict__ 注入）"""

    def test_when_available_sets_registry_on_client(self):
        mock_registry = MagicMock()
        mock_get = MagicMock(return_value=mock_registry)
        with patch.object(initialize, "VLLM_METRICS_AVAILABLE", True):
            with patch.dict(initialize.__dict__, {"get_prometheus_registry": mock_get}, clear=False):
                client = MagicMock()
                initialize.set_vllm_registry(client)
                assert client.registry == mock_registry

    def test_when_import_fails_logs_warning(self):
        mock_get = MagicMock(side_effect=ImportError("no vllm"))
        with patch.object(initialize, "VLLM_METRICS_AVAILABLE", True):
            with patch.dict(initialize.__dict__, {"get_prometheus_registry": mock_get}, clear=False):
                with patch("ms_service_profiler.patcher.vllm.metrics.initialize.logger") as mock_logger:
                    client = MagicMock()
                    initialize.set_vllm_registry(client)
                    mock_logger.warning.assert_called()


class TestSetVllmMetricPrefix:
    """测试 set_vllm_metric_prefix"""

    def test_sets_metric_prefix_on_client(self):
        client = MagicMock()
        initialize.set_vllm_metric_prefix(client)
        assert client.metric_prefix == initialize.VLLM_METRICS_PREFIX

    def test_prefix_constant_value(self):
        assert initialize.VLLM_METRICS_PREFIX == "vllm_profiling"


class TestSetupVllmMetrics:
    """测试 setup_vllm_metrics"""

    def test_setup_calls_multiprocess_registry_and_prefix(self):
        with patch.object(initialize, "set_vllm_multiprocess_prometheus") as mock_multi:
            with patch.object(initialize, "get_hook_metrics") as mock_get:
                with patch.object(initialize, "set_vllm_registry") as mock_reg:
                    with patch.object(initialize, "set_vllm_metric_prefix") as mock_prefix:
                        mock_client = MagicMock()
                        mock_get.return_value = mock_client
                        initialize.setup_vllm_metrics()
                        mock_multi.assert_called_once()
                        mock_get.assert_called_once()
                        mock_reg.assert_called_once_with(mock_client)
                        mock_prefix.assert_called_once_with(mock_client)
