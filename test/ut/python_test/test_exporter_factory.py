# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import pytest
from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.exporters.exporter_trace import ExporterTrace
from ms_service_profiler.exporters.exporter_req_status import ExporterReqStatus
from ms_service_profiler.exporters.exporter_req_data import ExporterReqData
from ms_service_profiler.exporters.exporter_batch import ExporterBatchData
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData
from ms_service_profiler.exporters.exporter_latency import ExporterLatency
from ms_service_profiler.exporters.exporter_pd_comm import ExporterPDComm

@pytest.fixture
def mock_args():
    """模拟初始化参数"""
    return {"config": "test_config"}

def test_create_exporters(mock_args):
    """测试创建所有支持的Exporter"""
    exporters = ExporterFactory.create_exporters(mock_args)
    assert len(exporters) == 7

def test_create_single_exporter(mock_args):
    """测试创建单个Exporter"""
    exporter = ExporterFactory.create("trace", mock_args)
    assert exporter == ExporterTrace
    assert exporter.name == "trace"

def test_create_unknown_exporter(mock_args):
    """测试创建未知的Exporter"""
    with pytest.raises(ValueError) as exc_info:
        ExporterFactory.create("unknown_exporter", mock_args)
    assert "未知的Exporter名称: unknown_exporter" in str(exc_info.value)

def test_exporter_initialization(mock_args):
    """测试Exporter初始化"""
    exporter = ExporterFactory.create("trace", mock_args)
    assert hasattr(exporter, "initialize")

def test_exporter_cls_list():
    """测试Exporter类的列表是否正确"""
    expected_classes = [
        ExporterTrace,
        ExporterReqStatus,
        ExporterReqData,
        ExporterBatchData,
        ExporterKVCacheData,
        ExporterLatency,
        ExporterPDComm,
    ]
    assert ExporterFactory.exporter_cls == expected_classes

def test_create_all_exporters(mock_args):
    """测试所有Exporter的创建和初始化"""
    exporters = ExporterFactory.create_exporters(mock_args)
    for exporter in exporters:
        assert exporter is not None
        assert hasattr(exporter, "initialize")