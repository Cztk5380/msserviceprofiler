# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from abc import abstractmethod
from typing import Dict
from ms_service_profiler.task.task import Task
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import Timer


class TaskExporterBase(Task):
    @classmethod
    @abstractmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def is_provide(cls, formats):
        return True

    @abstractmethod
    def do_export(self):
        pass

    def run(self):
        self.do_export()


class ExporterBase(TaskExporterBase):
    name: str = 'base'
    args = None
    
    def __init__(self, args=None) -> None:
        super().__init__(args if args is not None else self.args)

    @classmethod
    def depends(cls):
        return ["pipeline:service"]

    @classmethod
    @abstractmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @abstractmethod
    def export(cls, data: Dict) -> None:
        pass

    def run(self):
        if self._args is not None:
            self.initialize(self._args)
        data = self.get_depends_result("pipeline:service")
        if data is None:
            return
        with Timer(f"{self.name}-{self.task_index}", logger.info):
            self.export(data)