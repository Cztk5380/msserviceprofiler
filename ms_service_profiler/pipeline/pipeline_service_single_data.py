# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStampHelper


@Task.register("pipeline:service_single_data")
class PipelineServiceSingle(PipelineBase):
    @classmethod
    def depends(cls):
        return ["data_source:msprof", "data_source:db"]

    @classmethod
    def is_deal_single_data(cls):
        return True
    
    def run(self):
        data_list = self.get_depends_result("data_source:msprof") or self.get_depends_result("data_source:db")
        if not data_list:
            return None

        data = self.run_step(PluginTimeStampHelper, PluginTimeStampHelper.name, data_list)

        return data
