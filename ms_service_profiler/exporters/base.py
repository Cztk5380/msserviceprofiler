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
        with Timer(f"{self.name}-{self.task_index}", logger.debug):
            self.export(data)