# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from ms_service_profiler.exporters.exporter_trace import ExporterTrace
from ms_service_profiler.exporters.exporter_req_status import ExporterReqStatus
from ms_service_profiler.exporters.exporter_req_data import ExporterReqData
from ms_service_profiler.exporters.exporter_batch import ExporterBatchData
from ms_service_profiler.exporters.exporter_kvcache import ExporterKVCacheData
from ms_service_profiler.exporters.exporter_latency import ExporterLatency
from ms_service_profiler.exporters.exporter_pd_comm import ExporterPDComm
from ms_service_profiler.exporters.exporter_mspti import ExporterMspti
from ms_service_profiler.exporters.exporter_ep_balance import ExporterEpBalance
from ms_service_profiler.exporters.exporter_moe import ExporterMoe
from ms_service_profiler.exporters.exporter_forward import ExporterForwardData
from ms_service_profiler.exporters.exporter_coordinator import ExporterCoordinator


# 插件工厂类
class ExporterFactory:
    # exporter_cls = [ExporterTrace, ExporterReqStatus, ExporterReqData, ExporterBatchData, \
    #                 ExporterKVCacheData, ExporterLatency, ExporterPDComm, ExporterMspti, \
    #                 ExporterEpBalance, ExporterMoe, ExporterForwardData]
    exporter_cls = []
    @staticmethod
    def create_exporters(args):
        exporters = [ExporterCoordinator]
        # enable_exporter = ['trace', 'req_status', 'req_data', 'batch_data', 'kvcache_data', 'latency', 'pd_comm',
        #                    "ep_balance", "moe_analysis", "forward_data"]
        enable_exporter = ["coordinator"]

        for name in enable_exporter:
            exporters.append(ExporterFactory.create(name, args))
        return exporters

    @staticmethod
    def create_mspti_exporters(args):
        exporters = []
        enable_exporter = ['mspti', "ep_balance", "moe_analysis"]
        for name in enable_exporter:
            exporters.append(ExporterFactory.create(name, args))
        return exporters

    @staticmethod
    def create(name, args):
        for exporter in ExporterFactory.exporter_cls:
            if exporter.name == name:
                exporter.initialize(args)
                return exporter
        raise ValueError(f"未知的Exporter名称: {name}")
