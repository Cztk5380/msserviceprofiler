# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.processor.processor_res import ProcessorRes
from ms_service_profiler.processor.processor_req import ProcessorReq
from ms_service_profiler.plugins.plugin_common import PluginCommon
from ms_service_profiler.plugins.plugin_metric import PluginMetric
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus
from ms_service_profiler.plugins.plugin_concat import PluginConcat
from ms_service_profiler.plugins.plugin_trace import PluginTrace
from ms_service_profiler.plugins.plugin_process_name import PluginProcessName


@Task.register("pipeline:service")
class PipelineService(PipelineBase):
    @classmethod
    def depends(cls):
        return ["pipeline:service_single_data"]
    
    @timer(logger.debug)
    def run(self):
        data_list = self.get_depends_result("pipeline:service_single_data", [])
        if not data_list:
            return None

        data = ProcessorRes().parse(data_list)
        data = self.run_step(PluginConcat, PluginConcat.name, data)
        data = self.run_step(PluginCommon, PluginCommon.name, data, False)
        data = self.run_step(PluginReqStatus, PluginReqStatus.name, data, False)
        data = self.run_step(PluginMetric, PluginMetric.name, data, False)
        data = self.run_step(PluginTrace, PluginTrace.name, data, False)
        data = self.run_step(PluginProcessName, PluginProcessName.name, data, False)
        req_dict = ProcessorReq().parse(data.get("tx_data_df"))

        data.update(req_dict)
        return data
