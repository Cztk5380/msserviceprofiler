# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from abc import abstractmethod
from pathlib import Path
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.timer import Timer


class BaseDataSource(Task):
    def __init__(self, args) -> None:
        super().__init__(args)
        self.prof_path = None

    @staticmethod
    def get_filepaths(folder_path, file_pattern_map):
        file_path_map = {}
        for group_name, pattern in file_pattern_map.items():
            if isinstance(pattern, tuple):
                pattern, multi_file = pattern
            else:
                pattern, multi_file = pattern, False
            for fp in Path(folder_path).rglob(pattern):
                if multi_file:
                    file_path_map.setdefault(group_name, [])
                    file_path_map[group_name].append(str(fp))
                else:
                    file_path_map[group_name] = str(fp)
        return file_path_map

    @classmethod
    def get_prof_paths(cls, input_path: str):
        pass
    
    @classmethod
    def depends(cls):
        return ["prof_path"]

    @abstractmethod
    def load(self, prof_path):
        pass

    def run(self):
        self.set_prof_path(self.get_depends_result("prof_path"))
        with Timer(f"{self.name}-{self.task_index} load {self.prof_path}"):
            return self.load(self.prof_path)

    def set_prof_path(self, prof_path):
        self.prof_path = prof_path