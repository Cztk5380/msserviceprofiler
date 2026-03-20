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
"""
异常定义模块

定义所有自定义异常类，便于错误处理和调试。
"""


class ServiceMetricError(Exception):
    """ms_service_metric基础异常类"""

    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ConfigError(ServiceMetricError):
    """配置相关错误"""
    pass


class HandlerError(ServiceMetricError):
    """Handler相关错误"""
    pass


class SymbolError(ServiceMetricError):
    """Symbol相关错误"""
    pass


class HookError(ServiceMetricError):
    """Hook操作相关错误"""
    pass


class MetricsError(ServiceMetricError):
    """Metrics相关错误"""
    pass


class SharedMemoryError(ServiceMetricError):
    """共享内存相关错误"""
    pass
