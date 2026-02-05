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
from ms_service_profiler.patcher.core.module_hook import patcher


@patcher(
    ("sglang.srt.managers.detokenizer_manager", "DetokenizerManager.handle_batch_token_id_out"),
    min_version="0.5.4"
)
def handle_batch_token_id_out(original_func, this, recv_obj, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("Request").\
            res(recv_obj.rids).span_start("detokenize")

    ret = original_func(this, recv_obj, *args, **kwargs)

    prof.span_end()

    return ret


@patcher(
    ("sglang.srt.managers.tokenizer_manager", "TokenizerManager._tokenize_one_request"),
    min_version="0.5.4"
)
async def tokenize_one_request(original_func, this, obj, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("Request").res(str(obj.rid)).span_start("tokenize")
        
    ret = await original_func(this, obj, *args, **kwargs)

    prof.span_end()

    return ret


@patcher(
    ("sglang.srt.managers.tokenizer_manager", "TokenizerManager._batch_tokenize_and_process"),
    min_version="0.5.4"
)
async def batch_tokenize_and_process(original_func, this, batch_size, obj, *args, **kwargs):
    prof_list = []
    rid_list = []
    for i in range(batch_size):
        rid = obj[i].rid
        prof_list.append(
            Profiler(Level.INFO).domain("Request").span_start("tokenize").res(str(rid))
        )

    ret = await original_func(this, batch_size, obj, *args, **kwargs)

    for prof in prof_list:
        prof.span_end()

    return ret


@patcher(
    ("sglang.srt.managers.tokenizer_manager", "TokenizerManager._send_one_request"),
    min_version="0.5.4"
)
def send_one_request(original_func, this, obj, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("Request").span_start("send_to_scheduler.dispatch").\
        res(str(obj.rid))

    state = original_func(this, obj, *args, **kwargs)

    prof.span_end()

    return state


@patcher(
    ("sglang.srt.managers.tokenizer_manager", "TokenizerManager._send_batch_request"),
    min_version="0.5.4"
)
def send_batch_request(original_func, this, obj, tokenized_objs, *args, **kwargs):
    prof_rid_list = [tokenized_obj.rid for tokenized_obj in tokenized_objs]
    prof = Profiler(Level.INFO).domain("Request").\
        res(prof_rid_list).span_start("send_to_scheduler.dispatch")

    ret = original_func(this, obj, tokenized_objs, *args, **kwargs)

    prof.span_end()

    return ret


@patcher(
    ("sglang.srt.managers.tokenizer_manager", "TokenizerManager._wait_one_response"),
    min_version="0.5.4"
)
async def wait_one_response(original_func, this, obj, *args, **kwargs):
    is_stream = obj.stream

    async for response in original_func(this, obj, *args, **kwargs):
        Profiler(Level.INFO).domain("Request").attr("stream", is_stream)\
            .res(str(obj.rid)).event("httpRes")
        yield response


@patcher(
    hook_points=[
        ("sglang.srt.managers.io_struct", "GenerateReqInput.normalize_batch_and_arguments"),
        ("sglang.srt.managers.io_struct", "EmbeddingReqInput.normalize_batch_and_arguments")
    ],
    min_version="0.5.4"
)
def normalize_batch_and_arguments(original_func, this, *args, **kwargs):
    ret = original_func(this, *args, **kwargs)

    if this.is_single:
        bootstrap_room = (
            this.bootstrap_room if hasattr(this, "bootstrap_room") else None
        )
        Profiler(Level.INFO).domain("Request").res(str(this.rid)).\
            attr("bootstrap_room", bootstrap_room).event("httpReq")
    else:
        for i in range(len(this.rid)):
            bootstrap_room = (
                this.bootstrap_room[i]
                if hasattr(this, "bootstrap_room") and this.bootstrap_room
                else None
            )
            Profiler(Level.INFO).domain("Request").res(str(this.rid)).\
                attr("bootstrap_room", bootstrap_room).event("httpReq")

    return ret
