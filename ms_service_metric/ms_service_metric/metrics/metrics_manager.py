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
MetricsManager - Prometheus指标管理器

负责管理所有Prometheus指标的注册、记录和查询。
支持多种指标类型：Histogram、Counter、Gauge、Summary。
提供标签管理和表达式求值功能。
"""

import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
    Summary,
)
from prometheus_client import multiprocess

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.meta_state import get_meta_state, MetaState

logger = get_logger("metrics_manager")


# 默认的timer类型直方图分桶
# 覆盖从1ms到300s的范围，细粒度分布在常用区间
TIMER_BUCKETS = [
    0.001, 0.002, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05,
    0.06, 0.07, 0.08, 0.09, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35,
    0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
    # 细化1-10秒区间
    1.2, 1.4, 1.6, 1.8, 2.0,
    2.2, 2.4, 2.6, 2.8, 3.0,
    3.5, 4.0, 4.5, 5.0,
    5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0,
    # 保持长尾分布
    15.0, 20.0, 30.0, 40.0, 60.0, 90.0, 120.0, 180.0, 300.0
]

# 尺寸分桶配置
SIZE_BUCKETS = [
    0, 1, 10, 20, 30, 40, 50, 75, 100, 125, 150, 175, 200,
    300, 400, 500, 600, 700, 800, 900, 1000, 1500, 2000,
    2500, 3000, 4000, 5000, 6000, 7000, 8000, 10000,
    262144, float('inf')
]

class MetricType(str, Enum):
    """指标类型枚举"""
    TIMER = "timer"          # 耗时指标（使用Histogram实现）
    HISTOGRAM = "histogram"  # 直方图
    COUNTER = "counter"      # 计数器
    GAUGE = "gauge"          # 仪表盘
    SUMMARY = "summary"      # 摘要


@dataclass
class MetricConfig:
    """指标配置数据结构
    
    Attributes:
        name: 指标名称
        type: 指标类型
        expr: 表达式（对于非timer类型，用于计算指标值）
        buckets: 直方图分桶（可选，仅对timer和histogram类型有效）
        label: 标签定义列表（可选），格式为 [{"name": ..., "expr": ...}, ...]
    """
    name: str
    type: MetricType
    expr: str = ""
    buckets: Optional[List[float]] = None
    labels: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        """后初始化处理"""
        if self.type == MetricType.TIMER:
            # timer指标不需要expr，expr字段用于计算耗时
            self.expr = ""
        if self.labels is None:
            self.labels = {}

    def __repr__(self):
        return f"MetricConfig(name={self.name}, type={self.type}, t={type(self.type)}, expr={self.expr}, buckets={self.buckets}, labels={self.labels})"

    def get(self, key: str, default=None):
        """兼容字典访问方式
        
        为了兼容旧代码中使用 .get() 方法访问配置的方式
        """
        return getattr(self, key, default)


class MetricsManager:
    """Prometheus指标管理器
    
    负责管理所有指标的注册、记录和查询。
    支持多进程环境下的指标收集。
    
    Attributes:
        metrics: 存储指标对象，key为指标名称（带前缀）
        label_definitions: 存储标签定义，key为metric_name
        registry: Prometheus注册表
        metric_prefix: 指标名称前缀
    """
    
    def __init__(self):
        """初始化MetricsManager"""
        logger.debug("Initializing MetricsManager")
        
        # 存储指标对象，key为带前缀的指标名称
        self._metrics: Dict[str, Any] = {}
        
        # 存储标签定义，key为metric_name
        # 格式: {metric_name: [{"name": label_name, "expr": expr}, ...]}
        self._label_definitions: Dict[str, List[Dict[str, str]]] = {}
        
        # Prometheus注册表，延迟初始化
        self._registry: Optional[CollectorRegistry] = None
        
        # 指标名称前缀
        self._metric_prefix: str = ""
        
        logger.debug("MetricsManager initialized")
    
    @property
    def metric_prefix(self) -> str:
        """获取指标名称前缀"""
        return self._metric_prefix
    
    @metric_prefix.setter
    def metric_prefix(self, prefix: str):
        """设置指标名称前缀"""
        self._metric_prefix = prefix
        logger.debug(f"Set metric prefix: {prefix}")
    
    def _get_meta_state(self) -> MetaState:
        """获取元数据状态
        
        使用全局的get_meta_state()获取元数据状态，
        不需要外部设置。
        
        Returns:
            MetaState实例
        """
        return get_meta_state()
    
    @staticmethod
    def _get_appropriate_registry() -> CollectorRegistry:
        """获取合适的Prometheus注册表
        
        在多进程环境下创建新的registry并添加多进程收集器，
        否则使用默认registry。
        
        Returns:
            CollectorRegistry实例
        """
        # 检查是否在多进程环境下
        if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
            logger.debug("Using multi-process registry")
            # 多进程环境，创建新的registry并添加多进程收集器
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            return registry
        
        # 单进程环境，使用默认registry
        logger.debug("Using default registry")
        return REGISTRY
    
    def _generate_custom_buckets(self, max_end: float = 1000, max_precision: int = 6) -> List[float]:
        """生成自定义直方图分桶
        
        生成细粒度的分桶配置，只包含end <= max_end且precision <= max_precision的配置。
        
        Args:
            max_end: 分桶配置的最大end值，默认为1000
            max_precision: 最大精度（小数位数），默认为6
            
        Returns:
            分桶边界列表
        """
        # 基础配置
        all_bucket_configs = [
            {'start': 0, 'end': 0.001, 'step': 0.0001, 'precision': 4},
            {'start': 0, 'end': 0.0001, 'step': 0.00001, 'precision': 5},
            {'start': 0, 'end': 0.00001, 'step': 0.000001, 'precision': 6},
            {'start': 0, 'end': 0.01, 'step': 0.001, 'precision': 3},
            {'start': 0, 'end': 0.1, 'step': 0.01, 'precision': 2},
            {'start': 0, 'end': 1.0, 'step': 0.25, 'precision': 2},
            {'start': 1, 'end': 5, 'step': 0.5, 'precision': 1},
            {'start': 5, 'end': 25, 'step': 1, 'precision': 0},
            {'start': 25, 'end': 100, 'step': 25, 'precision': 0},
            {'start': 100, 'end': 500, 'step': 100, 'precision': 0},
            {'start': 500, 'end': 1000, 'step': 250, 'precision': 0}
        ]
        
        # 过滤配置：只保留end <= max_end且precision <= max_precision的配置
        bucket_configs = []
        for config in all_bucket_configs:
            if config['end'] <= max_end and config['precision'] <= max_precision:
                bucket_configs.append(config)
        
        buckets = [262144, float('inf')]
        
        for config in bucket_configs:
            start = config['start']
            end = config['end']
            step = config['step']
            precision = config['precision']
            
            if step > 0:
                val = start
                while val <= end + 1e-9:
                    if precision == 0:
                        buckets.append(int(round(val)))
                    else:
                        buckets.append(round(val, precision))
                    val += step
        
        buckets = sorted(list(set(buckets)))
        logger.debug(f"Generated {len(buckets)} custom buckets with max_end={max_end}, max_precision={max_precision}")
        return buckets
    
    def _add_prefix(self, metric_name: str) -> str:
        """为指标名称添加前缀
        
        Args:
            metric_name: 原始指标名称
            
        Returns:
            带前缀的指标名称
        """
        if self._metric_prefix:
            return f"{self._metric_prefix}_{metric_name}"
        return metric_name
    
    def _add_dp_label_name(self, label_names: Optional[List[str]] = None) -> List[str]:
        """为指标添加默认的dp域标签名
        
        Args:
            label_names: 原始标签名列表
            
        Returns:
            添加dp标签后的标签名列表
        """
        label_names = label_names or []
        
        if "dp" not in label_names:
            label_names = list(label_names)  # 创建副本避免修改原列表
            label_names.append("dp")
        if "role" not in label_names:
            label_names = list(label_names)  # 创建副本避免修改原列表
            label_names.append("role")
        
        return label_names
    
    def _add_dp_label_value(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """为指标添加默认的dp域标签值
        
        如果dp标签不存在，则尝试从meta_state获取dp_rank。
        
        Args:
            labels: 原始标签字典
            
        Returns:
            添加dp标签后的标签字典
        """
        labels = labels.copy() if labels is not None else {}
        
        meta_state = self._get_meta_state()
        # 尝试从meta_state获取dp_rank
        try:
            if "dp" not in labels:
                labels["dp"] = meta_state.dp_rank
        except Exception as e:
            logger.warning(f"Failed to get dp_rank from meta_state: {e}")
            labels["dp"] = "-1"
        
        labels["role"] = meta_state.get("role", "mixed")
        return labels
    
    def _sanitize_metric_name(self, name: str) -> str:
        """清理指标名称，确保符合Prometheus规范
        
        Prometheus指标名称规范：
        - 只能包含字母、数字、下划线和冒号
        - 不能以数字开头
        
        Args:
            name: 原始指标名称
            
        Returns:
            清理后的指标名称
        """
        # 替换不合规的字符（如连字符）
        sanitized = name.replace("-", "_")
        
        # 确保以字母开头
        if sanitized and sanitized[0].isdigit():
            sanitized = f"fn_{sanitized}"
        
        return sanitized
    
    def register_metric(
        self,
        metric_config: MetricConfig,
        label_names: Optional[List[str]] = None
    ) -> Optional[Any]:
        """注册指标
        
        根据配置创建对应的Prometheus指标对象。
        
        Args:
            metric_config: 指标配置
            label_names: 标签名列表
            
        Returns:
            创建的指标对象，如果失败则返回None
        """
        # 延迟初始化registry
        if self._registry is None:
            self._registry = self._get_appropriate_registry()
            logger.debug(f"Initialized registry: {self._registry}")
        
        # 使用带前缀的metric名称
        full_name = self._add_prefix(self._sanitize_metric_name(metric_config.name))
        
        # 添加dp标签
        labelnames = self._add_dp_label_name(label_names)
        
        metric_obj = None
        logger.debug(f"Registering metric: {full_name} with labels: {labelnames}, type: {metric_config.type}")
        
        try:
            if metric_config.type == MetricType.TIMER:
                # timer类型使用Histogram实现
                buckets = metric_config.buckets or TIMER_BUCKETS
                metric_obj = Histogram(
                    name=full_name,
                    documentation=f"Execution duration of {metric_config.name}",
                    labelnames=labelnames,
                    buckets=buckets,
                    registry=self._registry
                )
                logger.debug(f"Created timer metric: {full_name} with {len(buckets)} buckets")
                
            elif metric_config.type == MetricType.HISTOGRAM:
                # histogram类型
                buckets = metric_config.buckets or self._generate_custom_buckets()
                metric_obj = Histogram(
                    name=full_name,
                    documentation=f"Histogram for {metric_config.name}",
                    labelnames=labelnames,
                    buckets=buckets,
                    registry=self._registry
                )
                logger.debug(f"Created histogram metric: {full_name} with {len(buckets)} buckets")
                
            elif metric_config.type == MetricType.COUNTER:
                # counter类型
                metric_obj = Counter(
                    name=full_name,
                    documentation=f"Counter for {metric_config.name}",
                    labelnames=labelnames,
                    registry=self._registry
                )
                logger.debug(f"Created counter metric: {full_name}")
                
            elif metric_config.type == MetricType.GAUGE:
                # gauge类型，使用livemostrecent模式
                metric_obj = Gauge(
                    name=full_name,
                    documentation=f"Gauge for {metric_config.name}",
                    labelnames=labelnames,
                    registry=self._registry,
                    multiprocess_mode="livemostrecent"
                )
                logger.debug(f"Created gauge metric: {full_name}")
                
            elif metric_config.type == MetricType.SUMMARY:
                # summary类型
                metric_obj = Summary(
                    name=full_name,
                    documentation=f"Summary for {metric_config.name}",
                    labelnames=labelnames,
                    registry=self._registry
                )
                logger.debug(f"Created summary metric: {full_name}")
            
            if metric_obj:
                self._metrics[full_name] = metric_obj
                logger.info(f"Registered metric: {full_name} ({metric_config.type})")
        
        except ValueError as e:
            # 如果指标已经存在，从缓存中获取
            if full_name in self._metrics:
                logger.debug(f"Metric {full_name} already exists, using cached instance")
                metric_obj = self._metrics[full_name]
            else:
                logger.warning(f"Failed to create metric {full_name}: {e}")
        
        return metric_obj
    
    def add_label_definition(self, metric_name: str, label_name: str, expr: str):
        """添加标签定义
        
        为指定指标添加标签定义，标签值通过表达式计算。
        
        Args:
            metric_name: 指标名称
            label_name: 标签名称
            expr: 表达式字符串，用于计算标签值
        """
        # 使用带前缀的metric名称
        full_metric_name = self._add_prefix(self._sanitize_metric_name(metric_name))
        
        if full_metric_name not in self._label_definitions:
            self._label_definitions[full_metric_name] = []
        
        self._label_definitions[full_metric_name].append({
            "name": label_name,
            "expr": expr
        })
        
        logger.debug(f"Added label definition: {metric_name}.{label_name} = {expr}")
    
    def get_label_definitions(self) -> Dict[str, List[Dict[str, str]]]:
        """获取标签定义字典
        
        Returns:
            标签定义字典，格式为 {metric_name: [{"name": ..., "expr": ...}, ...]}
        """
        return self._label_definitions.copy()
    
    def record_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """记录指标值
        
        Args:
            metric_name: 指标名称
            value: 指标值
            labels: 标签字典
        """
        # 使用带前缀的metric名称
        full_metric_name = self._add_prefix(self._sanitize_metric_name(metric_name))
        
        # 添加dp标签
        labels = self._add_dp_label_value(labels)
        
        if full_metric_name not in self._metrics:
            logger.warning(f"Metric not found: {full_metric_name}")
            return
        
        metric_obj = self._metrics[full_metric_name]
        
        try:
            if isinstance(metric_obj, Histogram):
                # Histogram使用observe
                if labels:
                    metric_obj.labels(**labels).observe(value)
                else:
                    metric_obj.observe(value)
                    
            elif isinstance(metric_obj, Counter):
                # Counter使用inc
                inc_value = value if value > 0 else 1
                if labels:
                    metric_obj.labels(**labels).inc(inc_value)
                else:
                    metric_obj.inc(inc_value)
                    
            elif isinstance(metric_obj, Gauge):
                # Gauge使用set
                if labels:
                    metric_obj.labels(**labels).set(value)
                else:
                    metric_obj.set(value)
                    
            elif isinstance(metric_obj, Summary):
                # Summary使用observe
                if labels:
                    metric_obj.labels(**labels).observe(value)
                else:
                    metric_obj.observe(value)
            
            logger.debug(f"Recorded metric {full_metric_name}: {value} with labels {labels}")
            
        except Exception as e:
            logger.warning(f"Failed to record metric {metric_name}: {e}")
    
    def get_registry(self) -> Optional[CollectorRegistry]:
        """获取使用的registry
        
        Returns:
            CollectorRegistry实例或None
        """
        return self._registry
    
    def set_registry(self, registry: CollectorRegistry) -> None:
        """设置Prometheus registry
        
        用于外部设置自定义的registry，例如vLLM的prometheus registry。
        
        Args:
            registry: CollectorRegistry实例
        """
        self._registry = registry
        logger.debug(f"Set registry: {registry}")
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有已创建的指标
        
        Returns:
            指标名到指标对象的映射字典
        """
        return self._metrics.copy()
    
    def get_or_create_metric(
        self,
        metric_name: str,
        label_names: Optional[List[str]] = None,
        metric_type: MetricType = MetricType.TIMER,
        buckets: Optional[List[float]] = None
    ) -> "MetricsManager":
        """获取或创建指标
        
        如果指标不存在，则自动创建；如果已存在，则直接返回。
        该方法会正确处理metric_prefix，确保指标名称一致性。
        
        Args:
            metric_name: 指标名称（不含前缀）
            label_names: 标签名称列表
            metric_type: 指标类型
            buckets: 直方图分桶（可选）
            
        Returns:
            MetricsManager实例（self）
        """
        full_name = self._add_prefix(self._sanitize_metric_name(metric_name))
        if full_name not in self._metrics:
            metric_config = MetricConfig(
                name=metric_name,
                type=metric_type,
                expr="",
                buckets=buckets,
            )
            metric_obj = self.register_metric(metric_config, label_names=label_names)
            if metric_obj is None:
                logger.warning(f"Failed to register metric: {full_name}")
        
        return self
    
    def clear_metrics(self):
        """清除所有指标
        
        主要用于测试和重置场景。
        """
        self._metrics.clear()
        self._label_definitions.clear()
        logger.debug("Cleared all metrics")


# 全局MetricsManager实例
_metrics_manager_instance: Optional[MetricsManager] = MetricsManager()


def get_metrics_manager() -> MetricsManager:
    """获取全局MetricsManager实例（单例模式）

    Returns:
        MetricsManager单例实例
    """
    global _metrics_manager_instance
    if _metrics_manager_instance is None:
        _metrics_manager_instance = MetricsManager()
        logger.debug("Created global MetricsManager instance")
    return _metrics_manager_instance


def reset_metrics_manager():
    """Reset MetricsManager singleton, primarily for tests."""
    global _metrics_manager_instance
    _metrics_manager_instance = MetricsManager()
    logger.debug("Reset global MetricsManager instance")