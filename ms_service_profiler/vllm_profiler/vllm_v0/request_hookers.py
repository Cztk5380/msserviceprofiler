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
import os
import time

from ms_service_profiler import Profiler, Level
from ..module_hook import vllm_hook


def prof_add_request(request_id, prompt, *args, **kwargs):
    # 记录请求进入系统的时间
    Profiler(Level.INFO).domain("Request").res(request_id).event("httpReq")
    Profiler(Level.INFO).domain("Request").res(request_id).event("tokenize")


# generate -> add_request -> schedule -> execute_model
# 在请求进入引擎时记录时间戳，用于后续计算队列等待时间
@vllm_hook(
    hook_points=[
        ("vllm.engine.llm_engine", "LLMEngine.add_request"),
        ("vllm.engine.async_llm_engine", "AsyncLLMEngine.add_request"),
    ],
    min_version="0.6.3",
    max_version="0.6.3",
)
def add_request_063(original_func, this, request_id, prompt, *args, **kwargs):
    prof_add_request(request_id, prompt, *args, **kwargs)
    return original_func(this, request_id, prompt, *args, **kwargs)


@vllm_hook(("vllm.engine.llm_engine", "LLMEngine.add_request"), min_version="0.8.4")
def add_request_084(original_func, this, request_id, prompt, *args, **kwargs):
    prof_add_request(request_id, prompt, *args, **kwargs)
    return original_func(this, request_id, prompt, *args, **kwargs)


@vllm_hook(("vllm.engine.async_llm_engine", "AsyncLLMEngine.add_request"), min_version="0.8.4")
async def add_request_async(original_func, this, request_id, prompt, *args, **kwargs):
    prof_add_request(request_id, prompt, *args, **kwargs)
    return original_func(this, request_id, prompt, *args, **kwargs)


@vllm_hook(("vllm.engine.llm_engine", "LLMEngine._process_model_outputs"), min_version="0.8.4")
def process_model_outputs(original_func, this, ctx, request_id=None, *args, **kwargs):
    if len(ctx.output_queue) == 0:
        return original_func(this, ctx, request_id, *args, **kwargs)
    outputs, metadata_list, scheduler_outputs, _, _, _, skip = ctx.output_queue[0]
    ret = original_func(this, ctx, request_id, *args, **kwargs)

    request_id_list = []
    for ii, (sch_seq_group, meta) in enumerate(zip(scheduler_outputs.scheduled_seq_groups, metadata_list)):
        if ii in skip:
            continue

        seq_group, seq_request_id = sch_seq_group.seq_group, meta.request_id
        request_id_list.append(seq_request_id)
        if seq_group.is_finished() and len(seq_group.seqs) > 0:
            cur_seq = seq_group.seqs[0]
            profiler_recv = Profiler(Level.INFO).domain("Request").res(seq_request_id)
            profiler_reply = Profiler(Level.INFO).domain("Request").res(seq_request_id)
            profiler_recv.metric("recvTokenSize", cur_seq.get_prompt_len()).event("httpRes")
            profiler_reply.metric("replyTokenSize", cur_seq.get_output_len()).event("httpRes")

    prof = Profiler(Level.INFO).domain("Request").res(request_id_list)
    prof.event("detokenize")
    return ret


@vllm_hook(("vllm.engine.llm_engine", "LLMEngine.validate_output"), min_version="0.6.3", max_version="0.6.3")
def validate_output(original_func, this, output, output_type):
    profiler_recv = Profiler(Level.INFO).domain("Request")
    profiler_reply = Profiler(Level.INFO).domain("Request")
    if output.finished is True:
        request_id = output.request_id
        input_token_size = len(output.prompt_token_ids)
        output_token_size = len(output.outputs[0].token_ids)
        profiler_recv.res(request_id).metric("recvTokenSize", input_token_size).event("httpRes")
        profiler_reply.res(request_id).metric("replyTokenSize", output_token_size).event("httpRes")
    return original_func(this, output, output_type)
