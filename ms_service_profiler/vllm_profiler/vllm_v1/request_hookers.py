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


@vllm_hook(
    hook_points=[
        ("vllm.engine.async_llm_engine", "AsyncLLMEngine.add_request"),
        ("vllm.v1.engine.async_llm", "AsyncLLM.add_request")
    ],
    min_version="0.9.1"
)    
async def add_request_async(original_func, this, request_id, prompt, *args, **kwargs):
    Profiler(Level.INFO).domain("Engine").res(request_id).event("httpReq")
    Profiler(Level.INFO).domain("Engine").res(request_id).event("tokenize")
    return await original_func(this, request_id, prompt, *args, **kwargs)


@vllm_hook(("vllm.v1.engine.output_processor", "OutputProcessor.process_outputs"), min_version="0.9.1")
def process_outputs(original_func, this, engine_core_outputs, *args, **kwargs):
    if len(engine_core_outputs) == 0:
        return original_func(this, engine_core_outputs, *args, **kwargs)

    request_id_list = []
    for engine_core_output in engine_core_outputs:
        request_id = engine_core_output.request_id
        request_state = this.request_states.get(request_id)
        request_id_list.append(request_id)
        if request_state and engine_core_output.finish_reason is not None:
            recv_token_size = len(request_state.prompt_token_ids)
            reply_token_size = (request_state.stats.num_generation_tokens if request_state.stats else None)
            
            profiler = Profiler(Level.INFO).domain("Engine").res(request_id)
            profiler = profiler.\
                metric("recvTokenSize", recv_token_size).\
                metric("replyTokenSize", reply_token_size)
            profiler.event("httpRes")

    ret = original_func(this, engine_core_outputs, *args, **kwargs)
    prof = Profiler(Level.INFO).domain("Engine").res(request_id_list)
    prof.event("detokenize")
    return ret
