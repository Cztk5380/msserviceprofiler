# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import ParseError
from ms_service_profiler.processor.processor_res import ProcessorRes
from ms_service_profiler.plugins.plugin_common import PluginCommon
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStamp
from ms_service_profiler.plugins.plugin_metric import PluginMetric
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus
from ms_service_profiler.plugins.plugin_concat import PluginConcat
from ms_service_profiler.plugins.plugin_trace import PluginTrace
from ms_service_profiler.plugins.plugin_process_name import PluginProcessName
from ms_service_profiler.plugins.plugin_batch import PluginBatch


@Task.register("pipeline:service")
class PipelineService(PipelineBase):
    @classmethod
    def depends(cls):
        return ["data_source:msprof", "data_source:db"]
    
    @timer(logger.info)
    def run(self):
        data_list = self.get_depends_result("data_source:msprof", []) or []
        data_db = self.get_depends_result("data_source:db", None)
        if data_db is not None:
            data_list.extend(data_db)
        if not data_list:
            return None

        data = self.run_step(PluginTimeStamp, PluginTimeStamp.name, data_list)
        data = ProcessorRes().parse(data)
        data = self.run_step(PluginConcat, PluginConcat.name, data)
        data = self.run_step(PluginCommon, PluginCommon.name, data, False)
        data = self.run_step(PluginReqStatus, PluginReqStatus.name, data, False)
        data = self.run_step(PluginMetric, PluginMetric.name, data, False)
        data = self.run_step(PluginTrace, PluginTrace.name, data, False)
        data = self.run_step(PluginProcessName, PluginProcessName.name, data, False)
        data = self.run_step(PluginBatch, PluginBatch.name, data, False)

        return data
