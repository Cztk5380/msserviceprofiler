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
ms_service_metric.metrics - Metrics 管理模块

提供 Metrics 管理和元数据状态管理功能。
"""

from ms_service_metric.metrics.metrics_manager import (
    MetricsManager,
    MetricConfig,
    MetricType,
    get_metrics_manager,
    SIZE_BUCKETS,
)
from ms_service_metric.metrics.meta_state import get_meta_state, set_dp_rank

__all__ = [
    "MetricsManager",
    "MetricConfig",
    "MetricType",
    "get_metrics_manager",
    "SIZE_BUCKETS",
    "get_meta_state",
    "set_dp_rank",
]
