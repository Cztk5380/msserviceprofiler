# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import time
import functools
from ms_service_profiler.utils.log import logger


def timer(log_func=logger.debug):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()  # 记录开始时间
            result = func(*args, **kwargs)  # 执行函数
            end_time = time.perf_counter()  # 记录结束时间
            execution_time = end_time - start_time  # 计算执行时间
            log_func(f"{func.__qualname__} done in: {execution_time:.4f} s")
            return result
        return wrapper
    return decorator


class Timer:
    def __init__(self, name, log_func=logger.debug):
        self._name = name
        self._log_func = log_func
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()  # 记录开始时间
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        execution_time = time.perf_counter() - self.start_time  # 计算执行时间
        self._log_func(f"{self._name} done in: {execution_time:.4f} s")