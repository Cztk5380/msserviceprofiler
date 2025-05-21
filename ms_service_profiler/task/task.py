# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from abc import abstractmethod
from enum import Enum, auto
from ms_service_profiler.utils.error import ParseError


class DefaultValue(Enum):
    UNDEFINED = auto()


class Task():
    regist_map = dict()

    def __init__(self, args) -> None:
        self._args = args
        self._depends_output = dict()

    @classmethod
    def depends(cls):
        return []

    @classmethod
    def get_retister_by_name(cls, name: str):
        return cls.regist_map.get(name, None)

    @classmethod
    def register(cls, name):
        def decorator(task_type: type):
            cls.regist_map[name] = task_type
            return task_type
        return decorator
    
    @abstractmethod
    def run(self):
        pass

    def set_depends_result(self, name, data):
        self._depends_output[name] = data

    def get_depends_result(self, name, default_data=DefaultValue.UNDEFINED):
        if default_data is DefaultValue.UNDEFINED:
            value = self._depends_output.get(name, ParseError(f"need {name}'s result. but nothing found."))
            if isinstance(value, Exception):
                raise value
            return value
        else:
            return self._depends_output.get(name, default_data)