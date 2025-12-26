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

                matched_keys = [item for item in key_err.args if item in keys]

                # 创建包含所有缺失key的异常信息，但保持单个异常实例
                if len(matched_keys) == 1:
                    error_key = matched_keys[0]  # 单个key
                    error_msg = msg
                else:
                    error_key = matched_keys[0]  # 只用第一个key，保持与父类兼容
                    error_msg = f"{msg} Missing keys: {', '.join(str(k) for k in matched_keys)}"  # 包含所有缺失的key

                error = ColumnMissingError(error_key, error_msg)  # 仍然只创建一个异常实例

                if ignore:
                    logger.warning(error)
                    return None
                else:
                    raise error from key_err

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