# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Dict, List

from ...core.logger import logger
from ...core.metric_hook import HookMetrics, get_hook_metrics

# 首先尝试导入 vLLM 的 metrics 模块
try:
    from vllm.v1.metrics.prometheus import get_prometheus_registry
except ImportError:
    get_prometheus_registry = None  # type: ignore[misc, assignment]
    logger.warning("Metrics - vLLM metrics module not available, vllm hook metrics disabled")

VLLM_METRICS_AVAILABLE = get_prometheus_registry is not None

# Metric名称前缀
VLLM_METRICS_PREFIX = "vllm_profiling"


def set_vllm_multiprocess_prometheus():
    """设置vLLM metrics多进程环境"""
    if VLLM_METRICS_AVAILABLE:
        try:
            if "PROMETHEUS_MULTIPROC_DIR" not in os.environ:
                logger.warning(
                    "Missing environment variable 'PROMETHEUS_MULTIPROC_DIR' "
                    "will result in partial metrics loss. You are advised to run "
                    "'export PROMETHEUS_MULTIPROC_DIR=/path/to/your/existing/empty/directory'"
                )
            logger.info("Prometheus multiproc dir: %s", os.getenv("PROMETHEUS_MULTIPROC_DIR"))
        except Exception as e:
            logger.warning(f"Metics - Could not setup vLLM metrics: {e}")


def set_vllm_registry(metrics_client: HookMetrics):
    """
    获取vLLM特定的Prometheus registry，确保指标在同一个registry中
    """
    if VLLM_METRICS_AVAILABLE:
        try:
            # 使用vLLM的registry，确保指标在同一个registry中
            metrics_client.registry = get_prometheus_registry()
        except Exception as e:
            logger.warning(f"Metics - Could not get vLLM registry: {e}")


def set_vllm_metric_prefix(metrics_client: HookMetrics):
    """
    添加vLLM特定的指标前缀
    """
    metrics_client.metric_prefix = VLLM_METRICS_PREFIX


def setup_vllm_metrics():
    """
    初始化vllm metrics采集环境，确保新增metrics和vLLM原生指标同时显示
    """
    set_vllm_multiprocess_prometheus()

    metrics_client = get_hook_metrics()
    set_vllm_registry(metrics_client)
    set_vllm_metric_prefix(metrics_client)
