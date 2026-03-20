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
ms_service_metric.utils - 工具模块

包含各种实用工具函数和类，以及基础设施组件。
"""

from ms_service_metric.utils.expr_eval import evaluate_expression, ExprEval
from ms_service_metric.utils.function_context import FunctionContext
from ms_service_metric.utils.exceptions import (
    ServiceMetricError,
    ConfigError,
    HandlerError,
    SymbolError,
    HookError,
    SharedMemoryError,
)
from ms_service_metric.utils.logger import get_logger, setup_logging
from ms_service_metric.utils.shm_manager import (
    SharedMemoryManager,
    STATE_OFF,
    STATE_ON,
)

__all__ = [
    # 表达式求值
    "evaluate_expression",
    "ExprEval",
    # 函数上下文
    "FunctionContext",
    # 异常
    "ServiceMetricError",
    "ConfigError",
    "HandlerError",
    "SymbolError",
    "HookError",
    "SharedMemoryError",
    # 日志
    "get_logger",
    "setup_logging",
    # 共享内存
    "SharedMemoryManager",
    "STATE_OFF",
    "STATE_ON",
]
