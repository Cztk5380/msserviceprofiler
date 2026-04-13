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
import inspect
from contextlib import contextmanager
from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher
from ms_service_profiler.profiler import prof_step
from ms_service_profiler.mstx import service_profiler
from .utils import classify_requests, collect_request_ids, SharedHookState, create_state_getter
try:
    import torch_npu
    
    def synchronize(sync=True):
        if sync:
            torch_npu.npu.current_stream().synchronize()

except ImportError:
    def synchronize(_):
        pass

prof_current_step = 0

# 线程安全的全局状态
class HookState(SharedHookState):
    def __init__(self):
        super().__init__()
        self.forward_profiler = None
        self.execute_model_first_run = True
        self.begin_forward_first_run = True
        self.request_id_list = []
        # MTP/投机推理：仅 Decode 且启用 MTP 时由 mtp_handlers 写入，execute_model 消费
        self.mtp_num_accepted_by_req = {}  # Dict[str, int]
        self.mtp_num_draft_by_req = {}     # Dict[str, int]

    def clear_mtp(self):
        """消费后清空 MTP 状态，避免污染下一步"""
        self.mtp_num_accepted_by_req = {}
        self.mtp_num_draft_by_req = {}


# 线程本地存储获取器（每文件独立线程状态）
_get_state = create_state_getter(HookState)


def _normalize_req_id(req):
    if isinstance(req, dict):
        rid = req.get("rid")
        if rid is not None:
            return rid
    return req


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


def _finalize_execute_model_span(ret, prof):
    if prof is None:
        return ret

    add_done_callback = getattr(ret, "add_done_callback", None)
    if callable(add_done_callback):
        def _done_callback(_):
            prof.span_end()
        add_done_callback(_done_callback)
        return ret

    if inspect.isawaitable(ret):
        async def _await_and_finalize():
            try:
                return await ret
            finally:
                prof.span_end()
        return _await_and_finalize()

    prof.span_end()
    return ret


@patcher(
    hook_points=[
        ("vllm.v1.executor.abstract", "Executor.execute_model"),
        ("vllm.v1.executor.multiproc_executor", "MultiprocExecutor.execute_model"),
        ("vllm.v1.executor.uniproc_executor", "UniProcExecutor.execute_model"),
    ],
    min_version="0.9.1",
)
def execute_model(original_func, this, scheduler_output, *args, **kwargs):
    """处理执行模型钩子"""
    state = _get_state()
    request_id_list, request_id_with_iter_list, batch_type = classify_requests(state, scheduler_output)
    prof = None

    if request_id_list:
        prof = Profiler(Level.INFO).domain("Execute")
        prof.res(request_id_with_iter_list)
        prof.attr("batch_type", batch_type)
        prof.span_start("modelExec")
        prof.attr("batch_size", scheduler_output.total_num_scheduled_tokens)

        state.forward_profiler = Profiler(Level.INFO).domain("Execute").res(request_id_list)

    try:
        ret = original_func(this, scheduler_output, *args, **kwargs)
    except Exception:
        if prof is not None:
            prof.span_end()
        raise

    return _finalize_execute_model_span(ret, prof)


@patcher(
    hook_points=[
        ("vllm_ascend.worker.model_runner_v1", "NPUModelRunner.execute_model")
    ],
    min_version="0.9.1",
)
def execute_model_runner(original_func, this, scheduler_output, *args, **kwargs):
    """处理执行模型运行钩子"""
    global prof_current_step
    state = _get_state()
    request_id_list = collect_request_ids(scheduler_output)
    if request_id_list:
        prof = Profiler(Level.INFO).domain("Execute")
        prof.res(request_id_list)
        prof.span_start("modelRunnerExec")
        state.forward_profiler = Profiler(Level.INFO).domain("Execute").res(request_id_list)
        state.request_id_list = [_normalize_req_id(r) for r in request_id_list]

    ret = original_func(this, scheduler_output, *args, **kwargs)
    step_num = service_profiler.get_torch_prof_step_num()
    if step_num and step_num > 0:
        prof_step()
    else:
        prof_current_step += 1
        service_profiler.set_profiler_current_step(prof_current_step)

    if request_id_list:
        accepted_by_req = getattr(state, "mtp_num_accepted_by_req", None)
        if not accepted_by_req:
            accepted_by_req = _accepted_by_req_from_runner_output(ret)
        if accepted_by_req:
            prof.attr("spec_decode_accepted_by_req", accepted_by_req)
        if hasattr(state, "clear_mtp"):
            state.clear_mtp()
        prof.span_end()
    return ret


def _accepted_by_req_from_runner_output(ret):
    """从 execute_model_runner 返回值中解析每请求的 accepted 数，与 Draft 指标同源；sampled_token_ids 为已解析的有效 token 列表，一般长度为 accepted + 1（含最后一个 recovered/bonus token），故按 max(len(tokens)-1, 0) 计算。"""
    if ret is None:
        return None
    if hasattr(ret, "sampled_token_ids") and hasattr(ret, "req_ids"):
        ids = getattr(ret, "req_ids", None)
        tokens = getattr(ret, "sampled_token_ids", None)
        if ids and tokens:
            return {
                str(rid): max(len(tokens[i]) - 1, 0) if i < len(tokens) else 0
                for i, rid in enumerate(ids)
            }
    if hasattr(ret, "get_output"):
        try:
            out = ret.get_output()
            return _accepted_by_req_from_runner_output(out)
        except Exception:
            pass
    return None


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


@patcher(("vllm_ascend.utils", "ProfileExecuteDuration.capture_async"), min_version="0.9.1", max_version="0.14.0rc1")
@contextmanager
def capture_async(original_func, this, duration_tag, *args, **kwargs):
    """前向上下文钩子"""
    prof = Profiler(Level.INFO).domain("Execute").span_start(duration_tag)
    if duration_tag == "forward":
        state = _get_state()
        prof.res(state.request_id_list)
    synchronize(duration_tag == "forward")
    with original_func(this, duration_tag, *args, **kwargs) as ret:
        yield ret
    synchronize(duration_tag == "forward")
    prof.span_end()

@patcher(("vllm.v1.utils", "record_function_or_nullcontext"), min_version="0.15.0rc1")
@contextmanager
def record_function_or_nullcontext(original_func, name, *args, **kwargs):
    profiled_duration_tags = (
        "prepare input",
        "EPLB weight D2D",
        "forward",
        "post process",
        "sample_token",
        "draft_token",
        "EPLB update",
        "async_state_update",
    )
    # 不在上述列表中的 name 不进行 profiling
    if name not in profiled_duration_tags:
        with original_func(name, *args, **kwargs) as ret:
            yield ret
        return

    prof = Profiler(Level.INFO).domain("Execute").span_start(name)
    if name == "forward":
        state = _get_state()
        prof.res(state.request_id_list)
    synchronize(name == "forward")
    with original_func(name, *args, **kwargs) as ret:
        yield ret
    synchronize(name == "forward")
    prof.span_end()
