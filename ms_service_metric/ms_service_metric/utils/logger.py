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
日志工具模块

提供统一的日志记录功能，支持不同级别的日志输出。
"""

import logging
import os
import sys
from typing import Optional

# 默认日志格式
DEFAULT_FORMAT = "[%(asctime)s %(process)s %(name)s] %(levelname)s %(message)s"


def get_log_level():
    """获取日志级别，根据环境变量设置，默认为INFO"""
    log_level_str = os.getenv("PROF_LOG_LEVEL", "").upper()
    
    # 定义有效的日志级别映射
    log_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'WARN': logging.WARNING,  # 兼容写法
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
        'FATAL': logging.CRITICAL  # 兼容写法
    }
    
    # 返回环境变量对应的日志级别，否则返回默认值INFO
    return log_levels.get(log_level_str, logging.INFO)


def setup_logging(
    logger: logging.Logger,
    level: int = get_log_level(),
    format_string: str = DEFAULT_FORMAT,
    handler: Optional[logging.Handler] = None
) -> logging.Logger:
    """
    设置日志配置

    Args:
        level: 日志级别，默认为INFO
        format_string: 日志格式字符串
        handler: 自定义的日志处理器，默认为StreamHandler

    Returns:
        配置好的Logger实例
    """

    logger.propagate = False
    logger.setLevel(level)

    # 清除已有的handlers
    logger.handlers.clear()

    # 创建handler
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

    # 设置格式
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)

    # 添加handler
    logger.addHandler(handler)

    return logger


def get_logger(name: Optional[str] = "") -> logging.Logger:
    """
    获取logger实例

    Args:
        name: logger名称，如果为None则返回根logger

    Returns:
        Logger实例
    """
    logger = logging.getLogger(f"ms_service_metric.{name}")
    if not logger.handlers:
        logger = setup_logging(logger)
    return logger
