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
from contextlib import contextmanager
from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher
from .utils import classify_requests, SharedHookState, create_state_getter
try:
    import torch_npu
    
    def synchronize(sync=True):
        if sync:
            torch_npu.npu.current_stream().synchronize()

except ImportError:
    def synchronize(_):
        pass


# 线程安全的全局状态
class HookState(SharedHookState):
    def __init__(self):
        super().__init__()
        self.forward_profiler = None
        self.execute_model_first_run = True
        self.begin_forward_first_run = True


# 线程本地存储获取器（每文件独立线程状态）
_get_state = create_state_getter(HookState)


@patcher(
    hook_points=("vllm.model_executor.layers.logits_processor", "LogitsProcessor.forward"), 
    min_version="0.9.1"
)
def compute_logits(original_func, this, *args, **kwargs):
    """处理执行模型钩子"""
    prof = Profiler(Level.INFO).domain("Execute").span_start("computing_logits")
    synchronize()
    ret = original_func(this, *args, **kwargs)
    synchronize()
    prof.span_end()
    return ret


@patcher(hook_points=("vllm.v1.sample.sampler", "Sampler.forward"), min_version="0.9.1")
def sampler_forward(original_func, this, *args, **kwargs):
    """处理执行模型钩子"""
    prof = Profiler(Level.INFO).domain("Execute").span_start("sample")
    synchronize()
    ret = original_func(this, *args, **kwargs)
    synchronize()
    prof.span_end()
    return ret


@patcher(
    hook_points=[
        ("vllm.v1.executor.abstract", "Executor.execute_model"),
        ("vllm.v1.executor.multiproc_executor", "MultiprocExecutor.execute_model")
    ],
    min_version="0.9.1",
)
def execute_model(original_func, this, scheduler_output, *args, **kwargs):
    """处理执行模型钩子"""
    state = _get_state()
    request_id_list, request_id_with_iter_list, batch_type = classify_requests(state, scheduler_output)

    if request_id_list:
        prof = Profiler(Level.INFO).domain("Execute")
        prof.res(request_id_with_iter_list)
        prof.attr("batch_type", batch_type)
        prof.span_start("modelExec")
        prof.attr("batch_size", scheduler_output.total_num_scheduled_tokens)

        state.forward_profiler = Profiler(Level.INFO).domain("Execute").res(request_id_list)

    ret = original_func(this, scheduler_output, *args, **kwargs)
    if request_id_list:
        prof.span_end()
    return ret


@patcher(("vllm.forward_context", "set_forward_context"), min_version="0.9.1")
@contextmanager
def set_forward_context(original_func, *args, **kwargs):
    """前向上下文钩子"""
    state = _get_state()
    prof = Profiler(Level.INFO).domain("Execute") if state.forward_profiler is None else state.forward_profiler
    prof.span_start("set_forward_context")
    with original_func(*args, **kwargs):
        yield
    prof.span_end()
    if state.forward_profiler is not None:
        state.forward_profiler = None


@patcher(("vllm_ascend.utils", "ProfileExecuteDuration.capture_async"), min_version="0.9.1")
@contextmanager
def capture_async(original_func, this, duration_tag, *args, **kwargs):
    """前向上下文钩子"""
    prof = Profiler(Level.INFO).domain("Execute").span_start(duration_tag)
    synchronize(duration_tag == "forward")
    with original_func(this, duration_tag, *args, **kwargs) as ret:
        yield ret
    synchronize(duration_tag == "forward")
    prof.span_end()
