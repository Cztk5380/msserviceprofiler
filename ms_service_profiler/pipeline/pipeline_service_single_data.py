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
