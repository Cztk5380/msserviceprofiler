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
ms_service_metric - 动态函数Hook和性能监控库

该库提供了动态函数Hook功能，用于监控和分析服务性能。
支持通过共享内存和SIGUSR1信号进行动态开关控制。

主要组件:
    - SymbolHandlerManager: 核心管理类，管理所有handler和symbol
    - SymbolConfig: 配置管理类
    - Symbol: 代表一个需要hook的符号
    - Handler: Hook处理函数包装
    - MetricsManager: Metrics管理器
    - SymbolWatcher: 模块加载/卸载监视器
    - MetricControlWatch: Metric控制动态监视器

使用示例:
    >>> from ms_service_metric import SymbolHandlerManager
    >>> manager = SymbolHandlerManager()
    >>> manager.initialize()

控制命令:
    $ python -m ms_service_metric on      # 开启metric
    $ python -m ms_service_metric off     # 关闭metric
    $ python -m ms_service_metric restart # 重启metric

环境变量:
    MS_SERVICE_METRIC_SHM_PREFIX: 共享内存和信号量名称前缀 (默认: /ms_service_metric)
    MS_SERVICE_METRIC_MAX_PROCS: 最大进程数 (默认: 1000)
"""

__version__ = "26.0.0"

# 延迟导入映射表 - 新增导出类只需在此处添加条目
_LAZY_IMPORTS = {
    "SymbolHandlerManager": "ms_service_metric.core.symbol_handler_manager",
    "SymbolConfig": "ms_service_metric.core.config.symbol_config",
    "Symbol": "ms_service_metric.core.symbol",
    "Handler": "ms_service_metric.core.handler",
    "MetricsManager": "ms_service_metric.metrics.metrics_manager",
    "SymbolWatcher": "ms_service_metric.core.module.symbol_watcher",
    "MetricControlWatch": "ms_service_metric.core.config.metric_control_watch",
}

# 自动派生 __all__，确保与 _LAZY_IMPORTS 保持同步
__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name):
    """延迟导入，避免循环依赖"""
    if name in _LAZY_IMPORTS:
        module = __import__(_LAZY_IMPORTS[name], fromlist=[name])
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
