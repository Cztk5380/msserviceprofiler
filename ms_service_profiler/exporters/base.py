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
        with Timer(self.name, logger.info):
            self.do_export()


class ExporterBase(TaskExporterBase):
    name: str = 'base'
    
    @classmethod
    def depends(cls):
        return ["pipeline:service"]

    @classmethod
    @abstractmethod
    def initialize(cls, args):
        pass

    @classmethod
    @abstractmethod
    def export(cls, data: Dict) -> None:
        pass

    def run(self):
        self.initialize(self._args)
        data = self.get_depends_result("pipeline:service")
        if data is None:
            logger.debug(f"{self.name}: nothing to export")
            return
        with Timer(self.name, logger.info):
            self.export(data)