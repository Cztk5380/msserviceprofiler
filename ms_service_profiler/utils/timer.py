# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import time
import functools
from ms_service_profiler.utils.log import logger


def print_execution_time(name, execution_time, log_func):
    minutes, seconds = divmod(execution_time, 60)
    if minutes != 0:
        log_func(f"{name} done in: {minutes:.0f} min {seconds:.4f} s ({execution_time:.4f} s)")
    else:
        log_func(f"{name} done in: {execution_time:.4f} s")


def timer(log_func=logger.debug, log_enter=True):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()  # 记录开始时间
            if log_enter:
                log_func(f"{func.__qualname__} started")
            result = func(*args, **kwargs)  # 执行函数
            end_time = time.perf_counter()  # 记录结束时间
            print_execution_time(func.__qualname__, end_time - start_time, log_func)
            return result
        return wrapper
    return decorator


def time_record(name, last_record=None):
    now_time = time.perf_counter()
    if last_record is not None:
        print_execution_time(name, now_time - last_record, logger.debug)
    else:
        logger.debug(f"{name}")
    return now_time


class Timer:
    def __init__(self, name, log_func=logger.debug, log_enter=True):
        self._name = name
        self._log_func = log_func
        self.start_time = None
        self.state = "done"
        self.log_enter = log_enter

    def __enter__(self):
        self.start_time = time.perf_counter()  # 记录开始时间
        if self.log_enter:
            self._log_func(f"{self._name} started")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print_execution_time(self._name, time.perf_counter() - self.start_time, logger.debug)

    def set_done_state(self, state):
        self.state = state
