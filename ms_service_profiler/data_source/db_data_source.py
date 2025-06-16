# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from ms_service_profiler.data_source.base_data_source import BaseDataSource, Task
from ms_service_profiler.utils.error import LoadDataError


@Task.register("data_source:db")
class DBDataSource(BaseDataSource):
    @classmethod
    def get_prof_paths(cls, input_path: str):
        from ms_service_profiler.parse import get_filepaths
        file_filter = {
            "service": "ms_service_*.db"
        }

        filepaths = get_filepaths(input_path, file_filter)

        db_files = filepaths.get("service", [])
        if db_files:
            db_files = [db_files]

        return db_files

    def load(self, prof_path):
        db_files = prof_path
        from ms_service_profiler.parse import process
        return process(db_files)

