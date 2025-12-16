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
from ..module_hook import vllm_hook
from ..logger import logger


@vllm_hook(("vllm.v1.core.kv_cache_manager", "KVCacheManager.free"), min_version="0.9.1")
def free(original_func, this, request, *args, **kwargs):
    ret = original_func(this, request, *args, **kwargs)
    num_blocks = this.block_pool.get_num_free_blocks()
    usage_percent = this.usage
    prof = Profiler(Level.INFO).domain("Schedule.KVCache").res(request.request_id)
    prof.metric("deviceBlock", num_blocks) \
        .metric("UsagePercent", usage_percent) \
        .event("Free")
    return ret


@vllm_hook(("vllm.v1.core.kv_cache_manager", "KVCacheManager.get_computed_blocks"), min_version="0.9.1")
def get_computed_blocks(original_func, this, request, *args, **kwargs):
    ret = original_func(this, request, *args, **kwargs)
    if len(ret) > 1 and request.num_tokens > 0:
        num_new_computed_tokens = ret[1]
        cur_hit_rate = num_new_computed_tokens / request.num_tokens
        prof = Profiler(Level.INFO).domain("Schedule.KVCache").res(request.request_id)
        prof.attr("hitCache", cur_hit_rate).event("CacheHitRate")
    return ret
