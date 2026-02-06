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

try:
    from sglang.srt.managers.io_struct import (
        TokenizedGenerateReqInput, TokenizedEmbeddingReqInput
    )
    from sglang.srt.disaggregation.utils import DisaggregationMode
except ImportError:
    # 创建模拟类型供测试使用
    TokenizedGenerateReqInput = type('TokenizedGenerateReqInput', (), {})
    TokenizedEmbeddingReqInput = type('TokenizedEmbeddingReqInput', (), {})
    
    class DisaggregationMode:
        NULL = 'null'
        PREFILL = 'prefill'
        DECODE = 'decode'

from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher


def prof_get_batch_rids(batch):
    return [str(req.rid) for req in batch.reqs]


def get_batch_type(batch):
    if batch.forward_mode.is_decode():
        return "decode"
    elif batch.forward_mode.is_extend():
        return "prefill"
    return "unknown"


def prof_kvcache_info(scheduler, name="allocate"):
    if scheduler.is_hybrid:
        (
            _,
            _,
            _,
            _,
            full_available_size,
            full_evictable_size,
            swa_available_size,
            swa_evictable_size,
        ) = scheduler._get_swa_token_info()
        Profiler(Level.INFO).domain("KVCache")\
            .metric("deviceBlock", full_available_size)\
            .metric("fullEvictableSize", full_evictable_size)\
            .metric("swaAvailableSize", swa_available_size)\
            .metric("swaEvictableSize", swa_evictable_size)\
            .event(name)
    else:
        _, _, available_size, evictable_size = scheduler._get_token_info()
        Profiler(Level.INFO).domain("KVCache").metric("deviceBlock", available_size)\
            .metric("fullEvictableSize", evictable_size)\
            .event(name)


@patcher(
    ("sglang.srt.managers.scheduler", "Scheduler.recv_requests"),
    min_version="0.5.4"
)
def recv_requests(original_func, this, *args, **kwargs):
    recv_reqs = original_func(this, *args, **kwargs)

    for req in recv_reqs:
        if isinstance(
            req, (TokenizedGenerateReqInput, TokenizedEmbeddingReqInput)
        ):
            Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).event("recvReq")

    return recv_reqs


@patcher(
    hook_points=[
        ("sglang.srt.managers.scheduler", "Scheduler.handle_generate_request"),
        ("sglang.srt.managers.scheduler", "Scheduler.handle_embedding_request"),
    ],
    min_version="0.5.4"
)
def request_dispatcher(original_func, this, recv_req, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("Schedule").span_start("processReq").\
        res(str(recv_req.rid))

    output = original_func(this, recv_req, *args, **kwargs)

    prof.span_end()

    return output


@patcher(
    ("sglang.srt.managers.scheduler", "Scheduler.get_next_batch_to_run"),
    min_version="0.5.4"
)
def get_next_batch_to_run(original_func, this, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("Schedule").span_start("batchFrameworkProcessing")

    batch = original_func(this, *args, **kwargs)

    if batch:
        prof_kvcache_info(this, "allocate")
        prof.attr("batch_type", get_batch_type(batch)).res(prof_get_batch_rids(batch))
        prof.span_end()

    return batch


@patcher(
    ("sglang.srt.managers.scheduler", "Scheduler.run_batch"),
    min_version="0.5.4"
)
def run_batch(original_func, this, batch, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("ModelExecute").span_start("modelExec").\
        res(prof_get_batch_rids(batch)).attr("batch_type", get_batch_type(batch))

    result = original_func(this, batch, *args, **kwargs)

    prof.span_end()

    return result


@patcher(
    ("sglang.srt.managers.scheduler", "Scheduler.process_batch_result"),
    min_version="0.5.4"
)
def process_batch_result(original_func, this, batch, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("ModelExecute").span_start("postprocess").\
        res(prof_get_batch_rids(batch)).attr("batch_type", get_batch_type(batch))

    result = original_func(this, batch, *args, **kwargs)

    prof.span_end()

    return result


@patcher(
    ("sglang.srt.managers.scheduler", "Scheduler._add_request_to_queue"),
    min_version="0.5.4"
)
def add_request_to_queue(original_func, this, req, is_retracted: bool = False, *args, **kwargs):
    if this.disaggregation_mode == DisaggregationMode.NULL:
        if not this._abort_on_queued_limit(req):
            Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).\
                metric_scope("QueueName", "WAITING").event("Enqueue")
            Profiler(Level.INFO).domain("Schedule").metric("QueueSize", len(this.waiting_queue)).\
                metric_scope("QueueName", "WAITING").event("Queue")
    elif this.disaggregation_mode == DisaggregationMode.PREFILL:
        Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).\
            metric_scope("QueueName", "PrefillBootstrap").event("Enqueue")
        Profiler(Level.INFO).domain("Schedule").metric("QueueSize", len(this.disagg_prefill_bootstrap_queue)).\
            metric_scope("QueueName", "PrefillBootstrap").event("Queue")
    elif this.disaggregation_mode == DisaggregationMode.DECODE:
        if not is_retracted:
            Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).\
                metric_scope("QueueName", "DecodePrealloc").event("Enqueue")
            Profiler(Level.INFO).domain("Schedule").metric("QueueSize", len(this.disagg_decode_prealloc_queue)).\
                metric_scope("QueueName", "DecodePrealloc").event("Queue")

    result = original_func(this, req, is_retracted, *args, **kwargs)

    return result


@patcher(
    ("sglang.srt.managers.scheduler", "Scheduler.get_new_batch_prefill"),
    min_version="0.5.4"
)
def get_new_batch_prefill(original_func, this, *args, **kwargs):
    new_batch = original_func(this, *args, **kwargs)
    if new_batch is None:
        return new_batch

    Profiler(Level.INFO).domain("Schedule").metric("QueueSize", len(this.waiting_queue)).\
        metric_scope("QueueName", "WAITING").event("Queue")
    
    for req in new_batch.reqs:
        Profiler(Level.INFO).domain("Schedule").res(str(req.rid)).\
            metric_scope("QueueName", "WAITING").event("Dequeue")

    return new_batch


@patcher(
    ("sglang.srt.managers.schedule_batch", "Req.init_next_round_input"),
    min_version="0.5.4"
)
def init_next_round_input(original_func, this, *args, **kwargs):
    ret = original_func(this, *args, **kwargs)

    if this.origin_input_ids != 0:
        Profiler(Level.INFO).domain("HitCache").\
            metric("hitRate", str(len(this.prefix_indices) / len(this.origin_input_ids))).\
            res(str(this.rid)).event("HitCache")

    return ret


@patcher(
    ("sglang.srt.managers.scheduler_output_processor_mixin",
     "SchedulerOutputProcessorMixin.process_batch_result_prefill"),
    min_version="0.5.4"
)
def process_batch_result_prefill(original_func, this, batch, *args, **kwargs):
    if this.is_generation:
        for req in batch.reqs:
            if this.enable_overlap and req.is_retracted and len(req.output_ids) > 0:
                continue

            not_finished = this.is_mixed_chunk and this.enable_overlap and \
                (req.finished() or req.is_retracted)
            if not_finished:
                continue

            if req.is_retracted:
                continue

            if req.is_chunked <= 0 and req.finished():
                Profiler(Level.INFO).domain("Request").res(str(req.rid)).\
                    metric("recvTokenSize", len(req.origin_input_ids)).\
                    metric("replyTokenSize", len(req.output_ids)).\
                    event("PrefillEnd")

    ret = original_func(this, batch, *args, **kwargs)

    prof_kvcache_info(this, "free")

    return ret


@patcher(
    ("sglang.srt.managers.scheduler_output_processor_mixin",
     "SchedulerOutputProcessorMixin.process_batch_result_decode"),
    min_version="0.5.4"
)
def process_batch_result_decode(original_func, this, batch, *args, **kwargs):
    prof_list = []
    for req in batch.reqs:
        if this.enable_overlap and (req.finished() or req.is_retracted):
            prof_list.append(None)
        elif req.is_retracted:
            prof_list.append(None)
        else:
            prof_list.append(Profiler(Level.INFO).domain("Request").span_start("DecodeEnd"))

    ret = original_func(this, batch, *args, **kwargs)

    for i, req in enumerate(batch.reqs):
        if req.finished() and prof_list[i] is not None:
            prof_list[i].res(str(req.rid)).\
                metric("recvTokenSize", len(req.origin_input_ids)).\
                metric("replyTokenSize", len(req.output_ids)).\
                span_end()

    prof_kvcache_info(this, "free")

    return ret