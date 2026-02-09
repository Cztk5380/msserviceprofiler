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
from ms_service_profiler.exporters.base import TaskExporterBase
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
    return type('Args', (object,), {"config": "test_config", "span": None, "output_path": "/tmp", "format": ["csv"]})


def test_create_exporters(mock_args):
    """测试创建所有支持的Exporter"""
    exporters = ExporterFactory.create_exporters(mock_args)
    assert isinstance(exporters, list)
    assert all(issubclass(exporter, TaskExporterBase) for exporter in exporters)


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


def test_create_all_exporters(mock_args):
    """测试所有Exporter的创建和初始化"""
    exporters = ExporterFactory.create_exporters(mock_args)
    assert isinstance(exporters, list)
    for exporter in exporters:
        assert issubclass(exporter, TaskExporterBase)
        assert hasattr(exporter, "initialize")
