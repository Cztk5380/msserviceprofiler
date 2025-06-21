# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from pathlib import Path

from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.error import LoadDataError
from ms_service_profiler.utils.log import logger


@Task.register("data_source:msprof")
class MsprofDataSource(BaseDataSource):

    @classmethod
    def get_prof_paths(cls, input_path: str):
        filepaths = []
        for dp in Path(input_path).glob("**/PROF_*"):
            filepaths.append(dp)

        return filepaths

    def load(self, prof_path):
        from ms_service_profiler.parse import load_prof, gen_msprof_command, run_msprof_command, \
                    clear_last_msprof_output, is_need_msprof

        file_filter = {
            "tx": "msproftx.db",
            "cpu": "host_cpu_usage.db",
            "memory": "host_mem_usage.db",
            "host_start": "host_start.log",
            "info": "info.json",
            "start_info": "start_info",
            "msprof": ("msprof_*.json", True)
        }
        cur_path = str(prof_path)
        if is_need_msprof(cur_path):
            command = gen_msprof_command(cur_path)
            clear_last_msprof_output(cur_path)
            run_msprof_command(command)
        filepaths = self.get_filepaths(prof_path, file_filter)
        try:
            data = load_prof(filepaths)
        except Exception as ex:
            raise LoadDataError(str(prof_path)) from ex

        return data
