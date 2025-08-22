# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from abc import abstractmethod
from enum import Enum, auto
from ms_service_profiler.utils.error import ParseError, OtherTaskError
from ms_service_profiler.task.task_register import register


class DefaultValue(Enum):
    UNDEFINED = auto()
    SEND_FINISHED = auto()


class Task():
    def __init__(self, args) -> None:
        self._args = args
        self._depends_output = dict()
        self.task_name = None
        self.task_index = None
        self.recv_queue = None
        self.send_queue = None

    @classmethod
    def depends(cls):
        return []

    @classmethod
    def outputs(cls):
        return [cls.name]
    
    @classmethod
    def register(cls, name=None):
        return register(name)
    
    def init(self, task_name, task_index, recv_msg, send_queue):
        self.task_name = task_name
        self.task_index = task_index
        self.recv_msg = recv_msg
        self.send_queue = send_queue
        
    def gather(self, data, dst=0):
        # 只有dst 会等待
        self.send_queue.put((self.task_name, self.task_index, "gather", (dst, data)))
        if dst == self.task_index:
            _, gather_data = self.recv_msg()
            return gather_data
        else:
            return None
    
    def all_gather(self, data):
        # 所有都会等待
        self.send_queue.put((self.task_name, self.task_index, "all_gather", data))
        _, gather_data = self.recv_msg()
        return gather_data
    
    def all_gather_async(self, data):
        # 所有都会等待
        self.send_queue.put((self.task_name, self.task_index, "all_gather", data))
    
    def broadcast(self, src=0, data=None):
        # 所有都会等待, 发送会虽然有自己的数据，但是还是等待
        if self.task_index == src:
            self.send_queue.put((self.task_name, self.task_index, "broadcast", data))
        _, broadcast_data = self.recv_msg()
        return broadcast_data
    
    def send(self, data=None, dst=0):
        # 所有都会等待, 发送会虽然有自己的数据，但是还是等待
        self.send_queue.put((self.task_name, self.task_index, "send_to", (dst, data)))
        
    def send_finish(self):
        # 所有进程都会等待全部FINISHED
        return self.all_gather(DefaultValue.SEND_FINISHED)
    
    def recv_until_finish(self):
        # 一直收数据，直到结束
        self.all_gather_async(DefaultValue.SEND_FINISHED)
        msg = 'p2p'
        while msg== 'p2p':
            msg, recv_data = self.recv_msg()
            _, data = recv_data
            yield data
    
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
