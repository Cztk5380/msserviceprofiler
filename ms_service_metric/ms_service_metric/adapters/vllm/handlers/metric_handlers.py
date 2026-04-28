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
vLLM Metric Handlers (v1)

从重构前的 ms_service_profiler/patcher/vllm/handlers/v1/metric_handlers.py 迁移
提供vLLM v1特定的metric处理函数。
"""

import time
from typing import Any

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.metrics_manager import get_metrics_manager, MetricType, SIZE_BUCKETS
from ms_service_metric.adapters.vllm.handlers.utils import (
    clear_request_phase_state as _clear_request_phase_state,
    collect_phase_metrics as _collect_phase_metrics,
    get_scheduler_phase_state as _get_scheduler_phase_state,
)

logger = get_logger(__name__)
metrics_client = get_metrics_manager()


class Timeline:
    """时间线记录器
    
    用于记录和计算特定时间段内的耗时。
    """
    duration_config = {
        "npu:forward_duration": ("forward", "model_runner_get_output"),
        "npu:kernel_launch": ("forward", "post process"),
    }

    def __init__(self):
        self.time_record_set = {value[0] for value in self.duration_config.values()}
        self.duration_activate_dict = {
            trigger: (start, metric)
            for metric, (start, trigger) in self.duration_config.items()
        }
        self.time_recorded = {}
        # 预创建指标（性能优化）
        for metric_name in self.duration_config.keys():
            metrics_client.get_or_create_metric(metric_name)

    def record(self, name, start_time, duration):
        """记录时间点
        
        Args:
            name: 记录名称
            start_time: 开始时间
            duration: 持续时间
        """
        if name in self.time_record_set:
            self.time_recorded[name] = (start_time, start_time + duration)

        if name in self.duration_activate_dict:
            start_name, metric_name = self.duration_activate_dict[name]
            if self.time_recorded.get(start_name) is None:
                return
            end_time = start_time + duration
            start_time = self.time_recorded[start_name][0]
            metrics_client.record_metric(metric_name, end_time - start_time, {})


timeline_recorder: Timeline = Timeline()


class TimingContextManager:
    """用于计时的上下文管理器包装类。

    包装原始的上下文管理器，在进入和退出时记录执行时间，
    并将耗时作为 timer 指标记录到 Prometheus。
    """

    def __init__(self, label_name: str, original_context: Any):
        """初始化计时上下文管理器。

        Args:
            label_name: 标签名称
            original_context: 原始上下文管理器
        """
        self.label_name = label_name
        self.original_context = original_context
        self.start_time: float = 0.0

    def __enter__(self):
        """进入上下文时开始计时。"""
        self.start_time = time.time()
        return self.original_context.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时记录耗时。"""
        if exc_type is None:
            duration = time.time() - self.start_time
            metrics_client.record_metric("record_function_or_nullcontext", duration, {"name": self.label_name})
            timeline_recorder.record(self.label_name, self.start_time, duration)
        return self.original_context.__exit__(exc_type, exc_val, exc_tb)


# 预创建指标（性能优化）
metrics_client.get_or_create_metric("record_function_or_nullcontext", ["name"])


def record_function_timer_hook(original_func, name, *args, **kwargs):
    """record_function_or_nullcontext 的 hook 处理函数。

    该函数用于 hook vLLM 的 record_function_or_nullcontext 函数，
    拦截其返回的上下文管理器，并包装为 TimingContextManager，
    从而实现对 with 语句块执行耗时的采集。

    Args:
        original_func: 原始的 record_function_or_nullcontext 函数
        name: 函数名称
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        TimingContextManager: 包装后的上下文管理器
    """
    original_context = original_func(name, *args, **kwargs)
    return TimingContextManager(name, original_context)


def record_function_timer_hook_vllm_ascend(original_func, self, name, *args, **kwargs):
    """vllm_ascend 的 record_function_or_nullcontext hook 处理函数。

    Args:
        original_func: 原始的 record_function_or_nullcontext 函数
        self: 实例对象
        name: 函数名称
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        TimingContextManager: 包装后的上下文管理器
    """
    original_context = original_func(self, name, *args, **kwargs)
    return TimingContextManager(name, original_context)


# 预创建指标（性能优化）
metrics_client.get_or_create_metric("worker:model_runner_get_output:duration")


def runner_get_output_hooker(original_func, *args, **kwargs):
    """ModelRunner.get_output 的 hook 处理函数。

    Args:
        original_func: 原始函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        原始函数返回值
    """
    start_time = time.time()
    ret = original_func(*args, **kwargs)
    duration = time.time() - start_time
    
    metrics_client.record_metric("worker:model_runner_get_output:duration", duration, {})
    timeline_recorder.record("model_runner_get_output", start_time, duration)
    return ret


# 预创建 scheduler 相关指标（性能优化）
metrics_client.get_or_create_metric("scheduler:duration")
metrics_client.get_or_create_metric("scheduler:batch_size", buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:running_queue_size", buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:seqlen:avg", metric_type=MetricType.GAUGE, buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:seqlen:sum", metric_type=MetricType.GAUGE, buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:phase_batch_size", ["req_phase"], buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric("scheduler:recompute_events", metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric("scheduler:phase_scheduled_token_counter", ["req_phase"], metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric(
    "scheduler:phase_scheduled_tokens",
    ["req_phase"],
    metric_type=MetricType.HISTOGRAM,
    buckets=SIZE_BUCKETS,
)


def scheduler_scheduler_hooker(original_func, self, *args, **kwargs):
    """Scheduler.schedule 的 hook 处理函数。

    Args:
        original_func: 原始函数
        self: Scheduler 实例
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        原始函数返回值
    """
    start_time = time.time()
    ret = original_func(self, *args, **kwargs)
    duration = time.time() - start_time
    phase_metrics = _collect_phase_metrics(_get_scheduler_phase_state(), ret)

    metrics_client.record_metric("scheduler:duration", duration)
    metrics_client.record_metric("scheduler:batch_size", len(ret.num_scheduled_tokens))
    metrics_client.record_metric("scheduler:running_queue_size", len(self.running))
    
    seqlen_sum = 0
    seqlen_cnt = len(ret.scheduled_new_reqs) + len(ret.scheduled_cached_reqs.num_computed_tokens)
    
    for req in ret.scheduled_new_reqs:
        seqlen_sum += req.num_computed_tokens

    for num_computed_token in ret.scheduled_cached_reqs.num_computed_tokens:
        seqlen_sum += num_computed_token
    seqlen_sum += ret.total_num_scheduled_tokens

    if seqlen_cnt > 0 and seqlen_sum > 0:
        metrics_client.record_metric("scheduler:seqlen:avg", seqlen_sum / seqlen_cnt)
    if seqlen_sum > 0:
        metrics_client.record_metric("scheduler:seqlen:sum", seqlen_sum)

    for req_phase, phase_values in phase_metrics.items():
        labels = {"req_phase": req_phase}
        batch_size = phase_values["batch_size"]
        scheduled_tokens_sum = phase_values["scheduled_tokens_sum"]
        if batch_size <= 0:
            continue
        metrics_client.record_metric("scheduler:phase_batch_size", batch_size, labels)
        metrics_client.record_metric("scheduler:phase_scheduled_tokens", scheduled_tokens_sum, labels)
        if scheduled_tokens_sum > 0:
            metrics_client.record_metric("scheduler:phase_scheduled_token_counter", scheduled_tokens_sum, labels)

    return ret


def scheduler_preempt_request_hooker(original_func, self, *args, **kwargs):
    """Record exact v1 recompute events.

    In current vLLM v1, Scheduler._preempt_request is the path that
    preempts a running request, frees its KV cache, and resets computed
    tokens so the request will recompute when scheduled again.
    """
    ret = original_func(self, *args, **kwargs)
    _clear_request_phase_state(_get_scheduler_phase_state(), *args, *kwargs.values(), ret)
    metrics_client.record_metric("scheduler:recompute_events", 1)
    return ret

