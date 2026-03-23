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
ms_service_metric.core - 核心模块

包含所有核心类和功能实现。
"""

# 从 utils 导入基础设施
from ms_service_metric.utils.logger import get_logger, setup_logging
from ms_service_metric.utils.exceptions import (
    ServiceMetricError,
    ConfigError,
    HandlerError,
    SymbolError,
    HookError,
)

# 从 core.config 导入配置
from ms_service_metric.core.config.symbol_config import SymbolConfig
from ms_service_metric.core.config.metric_control_watch import MetricControlWatch

# 从 core 导入核心类
from ms_service_metric.core.symbol import Symbol
from ms_service_metric.core.handler import Handler, HandlerType

# 从 core.hook 导入 Hook 工具
from ms_service_metric.core.hook.hook_helper import HookHelper
from ms_service_metric.core.hook.hook_chain import HookChain, HookNode

# 从 metrics 导入指标管理
from ms_service_metric.metrics.metrics_manager import (
    MetricsManager,
    MetricConfig,
    MetricType,
    get_metrics_manager,
)

# 从 core.module 导入模块监视
from ms_service_metric.core.module import SymbolWatcher, ModuleEvent, ModuleEventType

# 从 core 导入核心管理器
from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

__all__ = [
    # 日志
    "get_logger",
    "setup_logging",
    # 异常
    "ServiceMetricError",
    "ConfigError",
    "HandlerError",
    "SymbolError",
    "HookError",
    # 配置
    "SymbolConfig",
    "MetricControlWatch",
    # Symbol和Handler
    "Symbol",
    "Handler",
    "HandlerType",
    # Hook工具
    "HookHelper",
    "HookChain",
    "HookNode",
    # 指标管理
    "MetricsManager",
    "MetricConfig",
    "MetricType",
    "get_metrics_manager",
    # 模块监视
    "SymbolWatcher",
    "ModuleEvent",
    "ModuleEventType",
    # 核心管理器
    "SymbolHandlerManager",
]
