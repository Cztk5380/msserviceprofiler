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

from ms_service_profiler.pipeline.pipeline_base import PipelineBase
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.processor.processor_eplb_observe import ProcessorEplbObserve


@Task.register("pipeline:eplb_observe")
class PipelineEplbObserve(PipelineBase):
    @classmethod
    def depends(cls):
        return ["data_source:service"]

    def run(self):
        data = self.get_depends_result("data_source:service", None)
        if not data:
            return None

        data = data.get("tx_data_df")

        data_list = self.gather(data, dst=0)
        if data_list is None:
            return None

        data = self.run_step(ProcessorEplbObserve(), "ProcessorEplbObserve", data_list, is_key_step=False)

        return data
