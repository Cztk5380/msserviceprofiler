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
from ms_service_profiler import Profiler, Level

from ..module_hook import vllm_hook

GLOBAL_REQUEST_DICT = {}


@vllm_hook(("vllm.core.block_manager", "SelfAttnBlockSpaceManager.allocate"), min_version="0.6.3")
def allocate(original_func, this, seq_group, *args, **kwargs):
    profiler = Profiler(Level.INFO)
    original_func(this, seq_group, *args, **kwargs)
    GLOBAL_REQUEST_DICT[seq_group.request_id] = seq_group.seqs
    prof = profiler.domain("KVCache").res(seq_group.request_id)
    prof.metric("deviceBlock", len(this.block_tables)).event("Allocate")


@vllm_hook(("vllm.core.block_manager", "SelfAttnBlockSpaceManager.append_slots"), min_version="0.6.3")
def append_slots(original_func, this, seq, num_lookahead_slots, *args, **kwargs):
    profiler = Profiler(Level.INFO)
    request_id = seq.seq_id
    for k, v in GLOBAL_REQUEST_DICT.items():
        if seq in v:
            request_id = k
            break
    new_cows = original_func(this, seq, num_lookahead_slots, *args, **kwargs)
    num_blocks = len(getattr(this.block_tables.get(seq.seq_id), "_blocks", []))
    prof = profiler.domain("KVCache").res(request_id)
    prof.metric("deviceBlock", len(this.block_tables)).event("AppendSlot")
    # This is called for every decoder process, recording current blocks
    profiler.domain("KVCache").res(request_id).metric("deviceBlock", num_blocks).event("blocks")
    return new_cows


@vllm_hook(("vllm.core.block_manager", "SelfAttnBlockSpaceManager.swap_in"), min_version="0.6.3")
def swap_in(original_func, this, seq_group, *args, **kwargs):
    profiler = Profiler(Level.INFO)
    res = original_func(this, seq_group, *args, **kwargs)
    prof = profiler.domain("KVCache").res(seq_group.request_id)
    prof.attr("swap", "swap_in").metric("deviceBlock", len(this.block_tables)).event("SwapIn")
    return res


@vllm_hook(("vllm.core.block_manager", "SelfAttnBlockSpaceManager.swap_out"), min_version="0.6.3")
def swap_out(original_func, this, seq_group, *args, **kwargs):
    profiler = Profiler(Level.INFO)
    res = original_func(this, seq_group, *args, **kwargs)
    prof = profiler.domain("KVCache").res(seq_group.request_id)
    prof.attr("swap", "swap_out").metric("deviceBlock", len(this.block_tables)).event("SwapOut")
    return res


@vllm_hook(("vllm.core.block_manager", "SelfAttnBlockSpaceManager.free"), min_version="0.6.3")
def free(original_func, this, seq, *args, **kwargs):
    profiler = Profiler(Level.INFO)
    request_id = seq.seq_id
    for k, v in GLOBAL_REQUEST_DICT.items():
        if seq in v:
            request_id = k
            break
    original_func(this, seq, *args, **kwargs)
    profiler.domain("KVCache").res(request_id).metric("deviceBlock", len(this.block_tables)).event("Free")


@vllm_hook(("vllm.engine.llm_engine", "LLMEngine._get_stats"), min_version="0.6.3")
def get_stats(original_func, this, *args, **kwargs):
    profiler = Profiler(Level.INFO)
    stats = original_func(this, *args, **kwargs)
    num_free_gpu = sum(scheduler.block_manager.get_num_free_gpu_blocks() for scheduler in this.scheduler)
    profiler.domain("KVCache").attr("cpuHitCache", stats.cpu_cache_usage_sys)
    profiler.attr("hitCache", stats.gpu_cache_usage_sys).event("GetCacheHitRate")
    profiler.domain("KVCache").attr("deviceFreeBlock", num_free_gpu).event("GetCacheHitRate")
    return stats
