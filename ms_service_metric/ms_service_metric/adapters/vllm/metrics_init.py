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
vLLM Metrics 初始化模块

从重构前的 ms_service_profiler/patcher/vllm/metrics/initialize.py 迁移
提供vLLM特定的metrics初始化功能。
"""

import os

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.metrics_manager import get_metrics_manager, MetricsManager

logger = get_logger(__name__)

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
            logger.warning(f"Metrics - Could not setup vLLM metrics: {e}")


def set_vllm_registry(metrics_client: MetricsManager):
    """
    获取vLLM特定的Prometheus registry，确保指标在同一个registry中
    
    Args:
        metrics_client: MetricsManager实例
    """
    if VLLM_METRICS_AVAILABLE:
        try:
            # 使用vLLM的registry，确保指标在同一个registry中
            metrics_client.set_registry(get_prometheus_registry())
            logger.debug("Set vLLM prometheus registry")
        except Exception as e:
            logger.warning(f"Metrics - Could not get vLLM registry: {e}")


def set_vllm_metric_prefix(metrics_client: MetricsManager):
    """
    添加vLLM特定的指标前缀
    
    Args:
        metrics_client: MetricsManager实例
    """
    metrics_client.metric_prefix = VLLM_METRICS_PREFIX
    logger.debug(f"Set vLLM metric prefix: {VLLM_METRICS_PREFIX}")


def setup_vllm_metrics():
    """
    初始化vllm metrics采集环境，确保新增metrics和vLLM原生指标同时显示
    
    应该在vLLM应用启动时调用此函数。
    """
    logger.info("Setting up vLLM metrics...")
    
    set_vllm_multiprocess_prometheus()

    metrics_client = get_metrics_manager()
    set_vllm_registry(metrics_client)
    set_vllm_metric_prefix(metrics_client)
    
    logger.info("vLLM metrics setup completed")
