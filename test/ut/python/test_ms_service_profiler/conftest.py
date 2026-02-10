# -------------------------------------------------------------------------
# conftest for test_ms_service_profiler: mock prometheus_client so UT
# does not require it to be installed in the test environment.
# -------------------------------------------------------------------------

import sys
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture(autouse=True)
def _cleanup_meta_path_mocks():
    """移除可能残留在 sys.meta_path 中的 Mock，避免影响后续测试的导入（如 find_spec().name 导致 KeyError）。"""
    yield
    try:
        sys.meta_path[:] = [x for x in sys.meta_path if not isinstance(x, (Mock, MagicMock))]
    except Exception:
        pass


# 在任意测试或 patcher 代码导入前注入 mock，避免 ModuleNotFoundError: No module named 'prometheus_client'
if "prometheus_client" not in sys.modules:
    _mock_prom = MagicMock()
    # 构造返回值：Histogram/Counter/Gauge/Summary 被调用时返回带 labels().observe/inc/set 的 mock
    _mock_metric_instance = MagicMock()
    _mock_metric_instance.labels.return_value = _mock_metric_instance
    _mock_prom.Histogram = MagicMock(return_value=_mock_metric_instance)
    _mock_prom.Counter = MagicMock(return_value=_mock_metric_instance)
    _mock_prom.Gauge = MagicMock(return_value=_mock_metric_instance)
    _mock_prom.Summary = MagicMock(return_value=_mock_metric_instance)
    _mock_prom.REGISTRY = MagicMock()
    _mock_prom.CollectorRegistry = MagicMock(return_value=MagicMock())
    _mock_prom.multiprocess = MagicMock()
    _mock_prom.multiprocess.MultiProcessCollector = MagicMock()
    sys.modules["prometheus_client"] = _mock_prom
