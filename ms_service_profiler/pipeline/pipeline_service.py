# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStampHelper
from ms_service_profiler.processor.processor_meta import ProcessorMeta
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
        return ["data_source:service"]

    def run(self):
        data = self.get_depends_result("data_source:service", None)
        if not data:
            return None

        data = self.run_step(PluginTimeStampHelper, PluginTimeStampHelper.name, data)

        meta_data = self.run_step(ProcessorMeta(), "ProcessorMeta", data)
        meta_data_list = self.all_gather(meta_data)

        data = self.run_step(ProcessorRes(), "ProcessorRes", data, meta_data, meta_data_list)
        data = self.run_step(PluginCommon, PluginCommon.name, data, is_key_step=False)
        data = self.run_step(PluginReqStatus, PluginReqStatus.name, data, is_key_step=False)
        data = self.run_step(PluginMetric, PluginMetric.name, data, is_key_step=False)  # 新增数据 metric_data_df
        data = self.run_step(PluginTrace, PluginTrace.name, data, is_key_step=False)
        data = self.run_step(PluginProcessName, PluginProcessName.name, data, is_key_step=False) # 新增数据 pid_label_map

        data_list = self.gather(data, dst=0)
        if data_list is None:
            return None

        data = self.run_step(PluginConcat, PluginConcat.name, data_list)
        req_dict = self.run_step(ProcessorReq(), "ProcessorReq", data.get("tx_data_df"))

        data.update(req_dict)
        return data
