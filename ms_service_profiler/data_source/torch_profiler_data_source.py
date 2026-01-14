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

import os
import json
import subprocess
from pathlib import Path

from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import find_all_file_complete


@Task.register("data_source:torch_profiler")
class TorchProfilerDataSource(BaseDataSource):

    @classmethod
    def outputs(cls):
        return ["data_source:torch_profiler"]

    @classmethod
    def get_prof_paths(cls, input_path: str):
        filepaths = []
        for dp in Path(input_path).rglob("**/*_ascend_pt"):
            if dp.is_dir():
                filepaths.append(dp)

        return filepaths

    @classmethod
    def is_need_torchprofiler(cls, full_path):
        torch_profiler_path = os.path.join(full_path, 'ASCEND_PROFILER_OUTPUT')
        if not os.path.isdir(torch_profiler_path):
            return True

        return False


    @classmethod
    def run_torch_profiler_parse(cls, full_path):
        try:
            import torch
            import torch_npu
            from torch_npu.profiler.profiler import analyse
        except ImportError as e:
            logger.warning("Required module not available: %s", str(e))
            return None
        
        try:
            result = analyse(profiler_path=full_path)
            logger.info("Successfully parsed msprof data from: %s", full_path)
            return result
            
        except Exception as e:
            logger.error("Failed to parse msprof data: %s", str(e))
            return None


    def load(self, prof_path):
        file_filter = {
            "torch_profiler": "trace_view.json",
        }
        cur_path = str(prof_path)
        if self.is_need_torchprofiler(cur_path):
            self.run_torch_profiler_parse(cur_path)
        filepaths = self.get_filepaths(prof_path, file_filter)
        filepaths['tx_data_df'] = None
        return filepaths