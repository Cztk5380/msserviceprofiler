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
from ms_service_profiler.profiler import prof_step
from ms_service_profiler.mstx import service_profiler
from ms_service_profiler.patcher.core.module_hook import patcher


@patcher(
    ("sglang.srt.model_executor.forward_batch_info", "ForwardBatch.init_new"),
    min_version="0.5.4"
)
def init_new(original_func, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("ModelExecute").span_start("preprocess")

    ret = original_func(*args, **kwargs)

    prof.span_end()

    return ret


@patcher(
    ("sglang.srt.model_executor.model_runner", "ModelRunner.forward"),
    min_version="0.5.4"
)
def forward(original_func, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("ModelExecute").span_start("forward")

    step_num = service_profiler.get_torch_prof_step_num()
    
    if step_num and step_num > 0:
        prof_step()

    output = original_func(*args, **kwargs)

    prof.span_end()

    return output


@patcher(
    ("sglang.srt.model_executor.model_runner", "ModelRunner.sample"),
    min_version="0.5.4"
)
def sample(original_func, *args, **kwargs):
    prof = Profiler(Level.INFO).domain("ModelExecute").span_start("sample")

    next_token_ids = original_func(*args, **kwargs)

    prof.span_end()

    return next_token_ids