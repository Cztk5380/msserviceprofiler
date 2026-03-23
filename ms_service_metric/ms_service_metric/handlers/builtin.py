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
Builtin Handlers - 内置Handler函数

提供常用的内置handler函数，可用于配置中直接使用。

使用示例:
    ```yaml
    - symbol: "my_module:my_function"
      handler: "ms_service_metric.handlers:default_handler"
      metrics:
        - name: "my_function_duration"
          type: timer
    ```

Handler函数签名:
    handler(original_func, *args, **kwargs) -> Any

    Args:
        original_func: 原始函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        原始函数的返回值
"""

import time
from typing import Any, Callable, Dict, List

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.metrics_manager import get_metrics_manager, MetricType, MetricConfig
from ms_service_metric.utils.expr_eval import ExprEval

logger = get_logger("builtin_handlers")


def _get_labels_for_metric(
    metric_name: str, context: Dict[str, Any], label_definitions: Dict[str, List[Dict[str, str]]]
) -> Dict[str, str]:
    """获取指标的标签值（内部辅助函数）

    根据标签定义的表达式计算标签值。

    Args:
        metric_name: 指标名称
        context: 表达式求值的上下文（包含变量值）
        label_definitions: 标签定义字典，格式为 {metric_name: [{"name": ..., "expr": ...}, ...]}

    Returns:
        标签名到标签值的映射字典
    """
    labels = {}

    # 计算标签值
    if metric_name in label_definitions:
        for label_def in label_definitions[metric_name]:
            label_name = label_def["name"]
            expr = label_def["expr"]

            if not expr:
                continue

            try:
                label_value = ExprEval(expr)(context)
                labels[label_name] = str(label_value)
                logger.debug(f"Evaluated label {label_name} = {label_value} for {metric_name}")
            except Exception as e:
                logger.warning(f"Failed to evaluate label expression '{expr}' " f"for metric '{metric_name}': {e}")
                continue

    return labels


def default_handler(metrics_config: List[MetricConfig], is_async: bool = False, **kwargs) -> Callable:
    """
    创建默认handler

    创建一个支持metrics配置的默认timer handler。
    使用context handler（生成器函数）方式。

    根据metrics配置中是否包含expr字段决定是否需要locals：
    - 有expr：需要locals，创建2参数handler
    - 无expr：不需要locals，创建1参数handler

    配置格式与重构前保持一致：

    metrics:
        - name: metric_name
        type: timer
        label:
            - name: label_name
            expr: expression

    Args:
        config: handler配置，包含可选的metrics字段

    Returns:
        默认的timer handler生成器函数（context handler）
    """
    
    def _has_expr_key(obj) -> bool:
        """检查config中是否存在expr key"""
        if obj.get('expr'):
            return True
        if obj.get('labels'): # 有labels 必须要有 expr
            return True
        return False

    need_locals = any(_has_expr_key(x) for x in metrics_config)

    # 预编译表达式求值器和预创建指标
    expr_evaluators = {}
    label_evaluators = {}

    manager = get_metrics_manager()
    
    logger.debug("Precompiling metrics, creating metrics..., metrics_config: %s, need_locals: %s", metrics_config, need_locals)
    metric_names = ""
    for metric in metrics_config:
        metric_name = metric.get('name', '')
        metric_names += f"{metric_name},"
        metric_type = metric.get('type', MetricType.TIMER)
        expr = metric.get('expr', '')
        
        logger.debug(f"Compiling metric {metric_name}")
        # 预编译主表达式
        if expr:
            try:
                expr_evaluators[metric_name] = ExprEval(expr)
            except Exception as e:
                logger.warning(f"Failed to compile expr for metric {metric_name}: {e}")

        # 预编译 label 表达式
        label_exprs = {}
        for label_name, label_expr in metric.get('labels', {}).items():
            if label_name and label_expr:
                try:
                    label_exprs[label_name] = ExprEval(label_expr)
                except Exception as e:
                    logger.warning(f"Failed to compile label expr for {label_name}: {e}")
        if label_exprs:
            label_evaluators[metric_name] = label_exprs

        # 获取或创建指标
        manager.get_or_create_metric(
            metric_name=metric_name,
            metric_type=metric_type,
            buckets=metric.get('buckets'),
            label_names=list(label_exprs.keys()),
        )

    def _record_metrics_common(eval_context):
        """记录 metrics 的通用逻辑（两个分支共用）"""
        duration = eval_context.get('duration', 0)

        for metric in metrics_config:
            name = metric.get('name', '')
            metric_type_str = metric.get('type', 'timer')

            # 计算指标值
            if metric_type_str == 'timer':
                value = duration
            else:
                evaluator = expr_evaluators.get(name)
                if evaluator:
                    try:
                        logger.debug(f"Evaluating expression for metric {name}, context: {eval_context}")
                        value = evaluator(eval_context)
                    except Exception as e:
                        logger.debug(f"Failed to evaluate expr for metric {name}: {e}")
                        value = 1
                else:
                    value = 1

            # 计算 labels
            labels = {}
            label_exprs = label_evaluators.get(name, {})
            for label_name, evaluator in label_exprs.items():
                try:
                    logger.debug(f"Evaluating label expression for {label_name}, context: {eval_context}")
                    labels[label_name] = evaluator(eval_context)
                except Exception as e:
                    logger.debug(f"Failed to evaluate label expr for {label_name}: {e}")

            # 记录指标
            manager.record_metric(name, value, labels)

    if need_locals:
        # 需要 locals 的版本（context manager，使用 yield）
        logger.debug("Creating default timer handler with locals, metric_names: %s", metric_names)
        def default_timer_handler(ctx):
            """默认 timer handler（需要 locals），支持 metrics 配置

            Args:
                ctx: FunctionContext 对象，包含 return_value
                local_values: 函数的 locals 字典

            Yields:
                None
            """
            start_time = time.time()
            yield
            duration = time.time() - start_time

            eval_context = {
                'duration': duration,
                'ret': ctx.return_value,
                **ctx.local_values,
            }

            _record_metrics_common(eval_context)

        return default_timer_handler
    elif is_async:
        logger.debug("Creating default timer handler with async, metric_names: %s", metric_names)

        async def async_timer_handler(ori, *args, **kwargs):
            logger.debug("Async timer handler, metric_names: %s", metric_names)
            """异步 timer handler"""
            start_time = time.time()
            res = await ori(*args, **kwargs)
            duration = time.time() - start_time
            eval_context = {
                'duration': duration,
                'ret': res,
            }
            _record_metrics_common(eval_context)
            return res

        return async_timer_handler
    else:
        logger.debug("Creating default timer handler with sync, metric_names: %s", metric_names)

        def sync_timer_handler(ori, *args, **kwargs):
            logger.debug("sync timer handler, metric_names: %s", metric_names)
            """同步 timer handler"""
            start_time = time.time()
            res = ori(*args, **kwargs)
            duration = time.time() - start_time

            eval_context = {
                'duration': duration,
                'ret': res,
            }
            _record_metrics_common(eval_context)
            return res

        return sync_timer_handler
