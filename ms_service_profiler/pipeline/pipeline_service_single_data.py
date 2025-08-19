# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStampHelper
from ms_service_profiler.utils.timer import Timer


@Task.register("pipeline:service_single_data")
class PipelineServiceSingle(PipelineBase):
    @classmethod
    def depends(cls):
        return ["data_source:service"]

    def run(self):
        data_list = self.get_depends_result("data_source:service")
        if not data_list:
            return None

        with Timer(f'{self.name} - {len(data_list.get("tx_data_df", []))}', log_enter=True):
            data = self.run_step(PluginTimeStampHelper, PluginTimeStampHelper.name, data_list)

        return data
