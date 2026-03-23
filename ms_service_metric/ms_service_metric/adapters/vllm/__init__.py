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
ms_service_metric.adapters.vllm - vLLM适配器

提供对vLLM推理框架的适配支持。
"""

from ms_service_metric.adapters.vllm.adapter import (
    initialize_vllm_metric,
    VLLMMetricAdapter,
)
from ms_service_metric.adapters.vllm.metrics_init import (
    set_vllm_metric_prefix,
    set_vllm_multiprocess_prometheus,
    set_vllm_registry,
    setup_vllm_metrics,
    VLLM_METRICS_PREFIX,
)

__all__ = [
    "initialize_vllm_metric",
    "set_vllm_metric_prefix",
    "set_vllm_multiprocess_prometheus",
    "set_vllm_registry",
    "setup_vllm_metrics",
    "VLLM_METRICS_PREFIX",
    "VLLMMetricAdapter",
]
