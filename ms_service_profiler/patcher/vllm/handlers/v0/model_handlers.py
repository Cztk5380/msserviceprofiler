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
import threading
from contextlib import contextmanager
from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher


# 线程安全的全局状态
class HookState:
    __slots__ = ("forward_profiler", "execute_model_first_run", "begin_forward_first_run")

    def __init__(self):
        self.forward_profiler = []
        self.execute_model_first_run = True
        self.begin_forward_first_run = True


# 线程本地存储
_thread_local = threading.local()


def _get_state() -> HookState:
    """获取线程本地状态"""
    if not hasattr(_thread_local, "hook_state"):
        _thread_local.hook_state = HookState()
    return _thread_local.hook_state


@patcher(
    hook_points=[
        ("vllm.executor.executor_base", "ExecutorBase.execute_model"),
        ("vllm.executor.executor_base", "DistributedExecutorBase.execute_model"),
    ],
    min_version="0.8.4",
)
def handle_execute_model(original_func, this, execute_model_req, *args, **kwargs):
    """处理执行模型钩子"""
    prof = Profiler(Level.INFO).domain("ModelExecute")
    is_prefill, request_id_list, request_id_with_iter_list = False, [], []
    for seq_metadata in execute_model_req.seq_group_metadata_list:
        if len(seq_metadata.seq_data) > 0:
            cur_seq_data = list(seq_metadata.seq_data.values())[0]
            iter_ = cur_seq_data.get_len() - len(cur_seq_data.prompt_token_ids)
        else:
            iter_ = 0
        request_id_list.append({"rid": seq_metadata.request_id})
        request_id_with_iter_list.append({"rid": seq_metadata.request_id, "iter": iter_})
        is_prefill = is_prefill or seq_metadata.is_prompt

    prof.res(request_id_with_iter_list)
    prof.attr("batch_type", "Prefill" if is_prefill else "Decode")
    prof.span_start("modelExec")
    prof.attr("batch_size", len(execute_model_req.seq_group_metadata_list))

    preprocess_prof = Profiler(Level.INFO).domain("ModelExecute").res(request_id_list)
    preprocess_prof.event("preprocess")

    ret = original_func(this, execute_model_req, *args, **kwargs)
    prof.span_end()
    return ret


@patcher(("vllm.worker.model_runner", "ModelRunner.execute_model"), min_version="0.6.3")
def execute_model(original_func, this, model_input, kv_caches, *args, **kwargs):
    """模型执行钩子"""
    state = _get_state()
    if state.execute_model_first_run:
        state.execute_model_first_run = False
        return original_func(this, model_input, kv_caches, *args, **kwargs)

    prof = Profiler(Level.INFO).domain("ModelExecute")
    prof.span_start("modelExec")

    ret = original_func(this, model_input, kv_caches, *args, **kwargs)

    is_prefill = model_input.attn_metadata.prefill_metadata

    request_id_list = []

    for request_id, _ in model_input.request_ids_to_seq_ids.items():
        request_id_list.append({"rid": request_id})

    prof.res(request_id_list)

    if is_prefill:
        prof.attr("batch_type", "Prefill")
    else:
        prof.attr("batch_type", "Decode")

    batch_size = model_input.input_tokens.shape[0]
    prof.attr("batch_size", batch_size)

    prof.span_end()
    return ret


@patcher(("vllm.attention.backends.utils", "CommonAttentionState.begin_forward"), min_version="0.6.3")
def begin_forward(original_func, this, model_input, *args, **kwargs):
    """前向开始钩子"""
    state = _get_state()
    result = original_func(this, model_input, *args, **kwargs)
    if state.begin_forward_first_run:
        state.begin_forward_first_run = False
        return result

    request_id_list = [{"rid": request_id} for request_id, _ in model_input.request_ids_to_seq_ids.items()]
    prof = Profiler(Level.INFO).domain("ModelExecute").res(request_id_list)
    state.forward_profiler.append(prof)
    return result


@patcher(("vllm.forward_context", "set_forward_context"), min_version="0.8.4")
@contextmanager
def set_forward_context(original_func, *args, **kwargs):
    """前向上下文钩子"""
    state = _get_state()
    if len(state.forward_profiler) > 0:
        prof = state.forward_profiler.pop(0)
        prof.span_start("forward")
    else:
        prof = None
    with original_func(*args, **kwargs):
        yield
    if prof is not None:
        prof.span_end()
