# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from ms_service_profiler.exporters.exporter_trace import ExporterTrace
from ms_service_profiler.exporters.exporter_req_status import ExporterReqStatus
from ms_service_profiler.exporters.exporter_req_data import ExporterReqData
from ms_service_profiler.exporters.exporter_batch import ExporterBatchData
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData
from ms_service_profiler.exporters.exporter_latency import ExporterLatency
from ms_service_profiler.exporters.exporter_summary import ExporterSummary


# 插件工厂类
class ExporterFactory:
    exporter_cls = [ExporterTrace, ExporterReqStatus, ExporterReqData, ExporterBatchData, \
        ExporterKVCacheData, ExporterLatency, ExporterSummary]

    @staticmethod
    def create_exporters(args):
        exporters = []
        enable_exporter = ['trace', 'req_status', 'req_data', 'batch_data', 'kvcache_data', 'latency']
        for name in enable_exporter:
            exporters.append(ExporterFactory.create(name, args))
        return exporters

    @staticmethod
    def create_summary_exporter(args):
        for exporter in ExporterFactory.exporter_cls:
            if exporter.name == 'summary':
                exporter.initialize(args)
                return exporter
        raise ValueError("ExporterSummary not found.")

    @staticmethod
    def create(name, args):
        for exporter in ExporterFactory.exporter_cls:
            if exporter.name == name:
                exporter.initialize(args)
                return exporter
        raise ValueError(f"未知的Exporter名称: {name}")
