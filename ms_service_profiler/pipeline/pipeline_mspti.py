# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import Timer
from ms_service_profiler.plugins import (PluginMsptiProcess, PluginEpBalanceProcess, PluginMoeSlowRankProcess)


@Task.register("pipeline:mspti")
class PipelineMspti(PipelineBase):
    @classmethod
    def depends(cls):
        return ["data_source:mspti"]
    
    def run(self):
        data = self.get_depends_result("data_source:mspti", None)
        if data is None:
            return None

        data = self.gather(data, dst=0)
        if data is None:
            return None
        with Timer(f"{self.name}-{self.task_index}"):
            data = self.run_step(PluginMsptiProcess, PluginMsptiProcess.name, data)
            data = self.run_step(PluginEpBalanceProcess, PluginEpBalanceProcess.name, data)
            data = self.run_step(PluginMoeSlowRankProcess, PluginMoeSlowRankProcess.name, data)

        return data
