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
from ms_service_profiler.exporters.exporter_eplb_observe import ExporterEplbObserve
from ms_service_profiler.exporters.exporter_forward import ExporterForwardData
from ms_service_profiler.exporters.exporter_coordinator import ExporterCoordinator
from ms_service_profiler.exporters.exporter_op_summary import ExporterOpSummaryCopier
from ms_service_profiler.exporters.exporter_span import ExporterSpan
from ms_service_profiler.exporters.exporter_statistic import ExporterStatistic


# 插件工厂类
class ExporterFactory:
    exporter_cls = [ExporterTrace, ExporterReqStatus, ExporterReqData, ExporterBatchData, \
                    ExporterKVCacheData, ExporterLatency, ExporterPDComm, ExporterMspti, \
                    ExporterEpBalance, ExporterMoe, ExporterForwardData, ExporterCoordinator, \
                    ExporterOpSummaryCopier, ExporterEplbObserve, ExporterSpan, ExporterStatistic]

    @staticmethod
    def create_exporters(args):
        exporters = []
        if args.span is not None:
            enable_exporter = ['span', 'statistic']
        else:
            enable_exporter = ['trace', 'req_status', 'req_data', 'batch_data', 'kvcache_data', 'latency', 'pd_comm',
                           "ep_balance", "moe_analysis", "forward_data", 'coordinator', 'op_summary_copier',
                           'expert_hot', 'statistic']

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