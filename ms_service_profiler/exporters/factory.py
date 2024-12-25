# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from ms_service_profiler.exporters.exporter_trace import ExporterTrace
from ms_service_profiler.exporters.exporter_detail import ExporterDetail
from ms_service_profiler.exporters.exporter_req_status import ExporterReqStatus
from ms_service_profiler.exporters.exporter_request import ExporterAnalyzeData
from ms_service_profiler.exporters.exporter_batch import ExporterBatchData
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData
from ms_service_profiler.exporters.exporter_latency import ExporterLatency


# 插件工厂类
class ExporterFactory:
    exporter_cls = [ExporterTrace, ExporterReqStatus, ExporterDetail, ExporterAnalyzeData, ExporterBatchData, \
        ExporterKVCacheData, ExporterLatency]

    @staticmethod
    def create_exporters(args):
        exporters = []
        for name in args.exporter:
            exporters.append(ExporterFactory.create(name, args))
        return exporters
    
    @staticmethod
    def create(name, args):
        for exporter in ExporterFactory.exporter_cls:
            if exporter.name == name:
                exporter.initialize(args)
                return exporter
        raise ValueError(f"未知的Exporter名称: {name}")
