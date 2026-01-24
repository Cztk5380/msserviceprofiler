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
from collections import Counter
from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher
from .utils import classify_requests, SharedHookState, create_state_getter


def compare_deques(queue1, queue2):
    counter1 = Counter(queue1)
    counter2 = Counter(queue2)
    diff = counter1 - counter2
    return diff


def queue_profiler(before_queue, after_queue, queue_name):
    # 队列元素减少
    less_queue = compare_deques(before_queue, after_queue)
    rid_list = []
    for seq_group in less_queue: # V1 note: SequenceGroup == Request
        rid_list.append(seq_group.request_id)
    if len(rid_list) > 0:
        prof = Profiler(Level.INFO).domain("Schedule").res(rid_list[:])
        prof.metric("QueueSize", len(after_queue)).metric_scope("QueueName", queue_name).event("Dequeue")

    # 队列元素增加
    add_queue = compare_deques(after_queue, before_queue)
    rid_list.clear()
    for seq_group in add_queue: # V1 note: SequenceGroup == Request
        rid_list.append(seq_group.request_id)
    if len(rid_list) > 0:
        prof = Profiler(Level.INFO).domain("Schedule").res(rid_list)
        prof.metric("QueueSize", len(after_queue)).metric_scope("QueueName", queue_name).event("Enqueue")


class HookState(SharedHookState):
    def __init__(self):
        super().__init__()


# 线程本地存储获取器（每文件独立线程状态）
_get_state = create_state_getter(HookState)


@patcher(
    hook_points=[
        ("vllm.v1.core.sched.scheduler", "Scheduler.schedule"),
        ("vllm_ascend.core.scheduler", "AscendScheduler.schedule")
    ],
    min_version="0.9.1"
)
def schedule(original_func, this, *args, **kwargs):
    state = _get_state()
    prof = Profiler(Level.INFO).domain("Schedule").span_start("batchFrameworkProcessing")

    # 获取KVCache状态
    kv_cache_manager = this.kv_cache_manager
    block_pool = kv_cache_manager.block_pool

    # 获取调度前的状态
    before_free_blocks = block_pool.get_num_free_blocks()
    total_blocks = this.kv_cache_config.num_blocks
    before_used_blocks = total_blocks - before_free_blocks

    before_running_queue = this.running.copy()
    before_waiting_queue = this.waiting.copy()
    scheduler_output = original_func(this, *args, **kwargs)

    # 获取调度后的状态
    after_usage = kv_cache_manager.usage
    after_free_blocks = block_pool.get_num_free_blocks()
    after_used_blocks = total_blocks - after_free_blocks
    allocated_blocks = after_used_blocks - before_used_blocks

    request_id_list, request_id_with_iter_list, batch_type = classify_requests(state, scheduler_output)

    if not request_id_list:
        return scheduler_output

    queue_profiler(before_running_queue, this.running, "RUNNING")
    queue_profiler(before_waiting_queue, this.waiting, "WAITING")
    prof.res(request_id_with_iter_list)

    if hasattr(scheduler_output, 'num_scheduled_tokens') and scheduler_output.num_scheduled_tokens:
        batch_req_ids = list(scheduler_output.num_scheduled_tokens.keys())
        kv_cache_prof = Profiler(Level.INFO).domain("Schedule.KVCache").res(batch_req_ids)
        kv_cache_prof.metric("TotalBlocks", total_blocks) \
            .metric("UsedBlocks", after_used_blocks) \
            .metric("FreeBlocks", after_free_blocks) \
            .metric("UsagePercent", after_usage) \
            .metric("AllocatedBlocks", allocated_blocks) \
            .metric("UsagePercent", after_usage) \
            .event("KVCacheStatus")

    prof.attr("batch_type", batch_type)
    prof.span_end()

    return scheduler_output


@patcher(("vllm.v1.core.sched.scheduler", "Scheduler.add_request"), min_version="0.9.1")
def add_request(original_func, this, request, *args, **kwargs):
    original_func(this, request, *args, **kwargs)
    prof_queue = Profiler(Level.INFO).domain("Schedule").res(request.request_id)
    prof_queue.metric("QueueSize", len(this.waiting)).metric_scope("QueueName", "WAITING").event("Enqueue")
