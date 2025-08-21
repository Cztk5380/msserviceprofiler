# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import functools
from ms_service_profiler.utils.log import logger


class ExportError(Exception):
    def __init__(self, message):
        super().__init__(message)  
        self.message = message

    def __str__(self):
        return f"ExportError: {self.message}"


class ParseError(Exception):
    def __init__(self, message):
        super().__init__(message) 
        self.message = message

    def __str__(self):
        return f"ParseError: {self.message}"


class OtherTaskError(Exception):
    def __init__(self, message):
        super().__init__(message) 
        self.message = message

    def __str__(self):
        return f"other task failed: {self.message}"



class MessageError(ParseError):
    pass


class DatabaseError(Exception):
    pass


class ValidationError(ParseError):
    def __init__(self, key, message="Failed to parse data"):
        super().__init__(message)
        self.key = key  
        self.message = message 

    def __str__(self):
        return f"{self.message}: {self.key}."


class KeyMissingError(ParseError):
    def __init__(self, key, message="Failed to parse data"):
        super().__init__(message)
        self.key = key

    def __str__(self):
        return f"{self.message}: {self.key} not exists."


class DataFrameMissingError(KeyMissingError):
    def __init__(self, key, message="Failed to read dataframe"):
        super().__init__(key, message)


class ColumnMissingError(KeyMissingError):
    def __init__(self, key, message="Failed to read column"):
        super().__init__(key, message)
        
    def __str__(self):
        return f"{self.message}: {self.key} not exists."

    def __eq__(self, other):
        return self.key == other.key and self.message == other.message


class LoadDataError(ParseError):
    def __init__(self, path, message="Failed to load data"):
        super().__init__(message)
        self.path = path  
        self.message = message  

    def __str__(self):
        # 返回详细的错误信息
        return f"{self.message}: {self.path}"


def key_except(*keys, ignore=False, msg=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)  # 执行函数
            except KeyError as key_err:
                if not hasattr(key_err, "args") or all(item not in keys for item in key_err.args):
                    raise key_err
                error = ColumnMissingError(key_err.args, msg)
                if ignore:
                    logger.warning(error)
                else:
                    raise error from key_err
            return None
        return wrapper
    return decorator


class KeyExcept:
    def __init__(self, *keys, ignore=False, msg=None):
        self.keys = keys
        self.ignore = ignore
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not KeyError:
            return False
        if not hasattr(exc_value, "args"):
            return False
        if all(item not in self.keys for item in exc_value.args):
            return False

        error = ColumnMissingError(exc_value.args, self.msg)
        if self.ignore:
            logger.warning(error)
        else:
            raise error from exc_value
        return True