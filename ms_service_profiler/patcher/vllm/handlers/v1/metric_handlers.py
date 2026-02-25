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

import time
from typing import Any
from ms_service_profiler.patcher.core.metric_hook import (
    MetricConfig,
    MetricType,
    get_hook_metrics,
    HookMetrics,
)


size_buckets = [
    0,
    1,
    10,
    20,
    30,
    40,
    50,
    75,
    100,
    125,
    150,
    175,
    200,
    300,
    400,
    500,
    600,
    700,
    800,
    900,
    1000,
    1500,
    2000,
    2500,
    3000,
    4000,
    5000,
    6000,
    7000,
    8000,
    10000,
    262144,
    float('inf'),
]


def _get_or_create_metric(metric_name, label_names=None, metric_type=MetricType.TIMER, buckets=None) -> HookMetrics:
    """获取或创建 timer 指标。

    Args:
        metric_name: 指标名称

    Returns:
        MetricConfig: 指标配置对象
    """
    metrics_client = get_hook_metrics()

    if metric_name not in metrics_client.metrics:
        # 创建 timer 类型的指标配置
        metric_config = MetricConfig(
            name=metric_name,
            type=metric_type,
            expr="",
            buckets=buckets,
        )
        _ = metrics_client.register_metric(metric_config, label_names=label_names)

    return metrics_client


class Timeline:
    duration_config = {
        "npu:forward_duration": ("forward", "model_runner_get_output"),
        "npu:kernel_launch": ("forward", "post process"),
    }

    def __init__(self):
        self.time_record_set = set((value[0] for _, value in self.duration_config.items()))  # 需要记录的set
        # 构建触发记录的字典：{触发名: (起始名, 指标名)}
        self.duration_activate_dict = {
            trigger: (start, metric)
            for metric, (start, trigger) in self.duration_config.items()
        }
        self.time_recorded = {}
        for metric_name in self.duration_config.keys():
            self.metrics_client = _get_or_create_metric(metric_name)

    def record(self, name, start_time, duration):
        if name in self.time_record_set:
            self.time_recorded[name] = (start_time, start_time + duration)

        if name in self.duration_activate_dict:
            start_name, metric_name = self.duration_activate_dict[name]
            if self.time_recorded.get(start_name) is None:
                return
            end_time = start_time + duration
            start_time = self.time_recorded[start_name][0]

            self.metrics_client.record_metric(metric_name, end_time - start_time, {})


timeline_recored = Timeline()
metrics_client: HookMetrics = _get_or_create_metric("record_function_or_nullcontext", ["name"])


class TimingContextManager:
    """用于计时的上下文管理器包装类。

    包装原始的上下文管理器，在进入和退出时记录执行时间，
    并将耗时作为 timer 指标记录到 Prometheus。
    """

    def __init__(self, label_name: str, original_context: Any):
        """初始化计时上下文管理器。

        Args:
            metric_name: 指标名称
            original_context: 原始上下文管理器
        """
        self.label_name = label_name
        self.original_context = original_context
        self.start_time: float = 0.0

    def __enter__(self):
        """进入上下文时开始计时。"""
        self.start_time = time.time()
        # 如果原始上下文管理器有 __enter__，调用它
        return self.original_context.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):

        # 只记录成功的调用（无异常）
        if exc_type is None:
            """退出上下文时记录耗时。"""
            duration = time.time() - self.start_time
            # 获取或创建指标
            metrics_client.record_metric("record_function_or_nullcontext", duration, {"name": self.label_name})
            timeline_recored.record(self.label_name, self.start_time, duration)

        # 如果原始上下文管理器有 __exit__，调用它
        return self.original_context.__exit__(exc_type, exc_val, exc_tb)


def record_function_timer_hook(original_func, name, *args, **kwargs):
    """record_function_or_nullcontext 的 hook 处理函数。

    该函数用于 hook vLLM 的 record_function_or_nullcontext 函数，
    拦截其返回的上下文管理器，并包装为 TimingContextManager，
    从而实现对 with 语句块执行耗时的采集。

    Args:
        original_func: 原始的 record_function_or_nullcontext 函数
        *args: 位置参数，第一个参数应为 name
        **kwargs: 关键字参数，可能包含 name

    Returns:
        TimingContextManager: 包装后的上下文管理器
    """
    # record_function_or_nullcontext(name: str) -> AbstractContextManager
    # 调用原函数获取原始上下文管理器
    original_context = original_func(name, *args, **kwargs)

    # 返回包装后的上下文管理器
    return TimingContextManager(name, original_context)


def record_function_timer_hook_vllm_ascend(original_func, self, name, *args, **kwargs):
    # 调用原函数获取原始上下文管理器
    original_context = original_func(self, name, *args, **kwargs)

    # 返回包装后的上下文管理器
    return TimingContextManager(name, original_context)


metrics_client: HookMetrics = _get_or_create_metric("worker:model_runner_get_output:duration")


def runner_get_output_hooker(original_func, *args, **kwargs):
    start_time = time.time()
    # 调用原函数获取原始上下文管理器
    ret = original_func(*args, **kwargs)
    duration = time.time() - start_time

    metrics_client.record_metric("worker:model_runner_get_output:duration", duration, {})
    timeline_recored.record("model_runner_get_output", start_time, duration)
    return ret


_ = _get_or_create_metric("scheduler:duration", label_names=["dp"])
_ = _get_or_create_metric("scheduler:batch_size", buckets=size_buckets, label_names=["dp"])
_ = _get_or_create_metric("scheduler:running_queue_size", buckets=size_buckets, label_names=["dp"])
_ = _get_or_create_metric("scheduler:seqlen:avg", metric_type=MetricType.GAUGE, buckets=size_buckets, label_names=["dp"])
_ = _get_or_create_metric("scheduler:seqlen:sum", metric_type=MetricType.GAUGE, buckets=size_buckets, label_names=["dp"])


def scheduler_scheduler_hooker(original_func, self, *args, **kwargs):
    start_time = time.time()
    # 调用原函数获取原始上下文管理器
    ret = original_func(self, *args, **kwargs)

    duration = time.time() - start_time

    metrics_client.record_metric("scheduler:duration", duration)
    metrics_client.record_metric("scheduler:batch_size", len(ret.num_scheduled_tokens))
    metrics_client.record_metric("scheduler:running_queue_size", len(self.running))
    seqlen_sum = 0
    seqlen_cnt = len(ret.scheduled_new_reqs) + len(ret.scheduled_cached_reqs.num_computed_tokens)
    for req in ret.scheduled_new_reqs:
        seqlen_sum += req.num_computed_tokens

    for num_computed_token in ret.scheduled_cached_reqs.num_computed_tokens:
        seqlen_sum += num_computed_token
    seqlen_sum += ret.total_num_scheduled_tokens  # 添加本次调度的token，这样prefill的数据更好看

    if seqlen_cnt > 0 and seqlen_sum > 0:
        metrics_client.record_metric("scheduler:seqlen:avg", seqlen_sum / seqlen_cnt)
    if seqlen_sum > 0:
        metrics_client.record_metric("scheduler:seqlen:sum", seqlen_sum)

    return ret
