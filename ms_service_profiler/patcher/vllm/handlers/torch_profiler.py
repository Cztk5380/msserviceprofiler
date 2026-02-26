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

from ms_service_profiler.mstx import service_profiler
from ms_service_profiler.profiler import Level
from ms_service_profiler.utils.log import logger
from ms_service_profiler.patcher.core.utils import get_shared_state

try:
    import torch
except ImportError:
    torch = None  # type: ignore

try:
    import torch_npu
except ImportError:
    torch_npu = None  # type: ignore

state = get_shared_state()
pointer = None

def register_torch_profiler():
    if torch_npu is None:
        logger.debug("torch_npu not available, skip register_torch_profiler")
        return
    patch_model_runner_with_torch_profiler_register()
    patch_model_runner_with_torch_profiler_enable()


def patch_model_runner_with_torch_profiler_enable():
    from vllm_ascend.worker.worker import NPUWorker

    def new_profile(self, is_start):
        if is_start:
            prof_build()
            prof_start()
        else:
            prof_stop()
    NPUWorker.profile = new_profile


def patch_model_runner_with_torch_profiler_register():
    import vllm.v1.engine.core
    from vllm.v1.engine.core import EngineCore

    original_init = EngineCore._initialize_kv_caches

    def new_init(self, *args, **kwargs):
        result = original_init(self, *args, **kwargs)
        global pointer
        if self is not None:
            pointer = self
            step_num = service_profiler.get_torch_prof_step_num()
            if service_profiler.is_torch_profiler_register() and step_num==0:
                torch_profiler_register()
        return result

    EngineCore._initialize_kv_caches = new_init


def prof_start_exec():
    global pointer
    pointer.model_executor.profile(True)


def prof_stop_exec():
    global pointer
    pointer.model_executor.profile(False)


def torch_profiler_register():
    start_result = service_profiler.register_profiler_start_callback(prof_start_exec)
    stop_result = service_profiler.register_profiler_stop_callback(prof_stop_exec)
    
    
def prof_build():
    if torch_npu is None:
        logger.debug("torch_npu not available, skip prof_build")
        return
    task_level_map = {
        "L0": torch_npu.profiler.ProfilerLevel.Level0,
        "L1": torch_npu.profiler.ProfilerLevel.Level1,
        "L2": torch_npu.profiler.ProfilerLevel.Level2
    }

    aicore_metrics_map = {
        0: torch_npu.profiler.AiCMetrics.ArithmeticUtilization,
        1: torch_npu.profiler.AiCMetrics.PipeUtilization,
        2: torch_npu.profiler.AiCMetrics.Memory,
        3: torch_npu.profiler.AiCMetrics.MemoryL0,
        4: torch_npu.profiler.AiCMetrics.ResourceConflictRatio,
        5: torch_npu.profiler.AiCMetrics.MemoryUB,
        6: torch_npu.profiler.AiCMetrics.L2Cache,
        8: torch_npu.profiler.AiCMetrics.MemoryAccess,
    }

    profiler_level = task_level_map.get(
        service_profiler.get_acl_task_time_level(), 
        torch_npu.profiler.ProfilerLevel.Level_none
    )
    
    aic_metrics = aicore_metrics_map.get(
        service_profiler.get_acl_prof_aicore_metrics(),
        torch_npu.profiler.AiCMetrics.AiCoreNone
    )

    experimental_config = torch_npu.profiler._ExperimentalConfig(
        export_type=torch_npu.profiler.ExportType.Text,
        profiler_level=profiler_level,
        msprof_tx=False,
        aic_metrics=aic_metrics,
        l2_cache=False,
        op_attr=False,
        data_simplification=False,
        record_op_args=False,
        gc_detect_threshold=None,
    )

    profiler_kwargs = {
        "activities": [torch_npu.profiler.ProfilerActivity.CPU, 
                    torch_npu.profiler.ProfilerActivity.NPU],
        "on_trace_ready": torch_npu.profiler.tensorboard_trace_handler(
            dir_name=service_profiler.get_prof_path(), 
            analyse_flag=False
        ),
        "record_shapes": True,
        "profile_memory": False,
        "with_stack": service_profiler.is_torch_prof_stack(),
        "with_modules": service_profiler.is_torch_prof_modules(),
        "with_flops": False,
        "experimental_config": experimental_config,
    }
    state = get_shared_state()
    with state._lock:
        state.torch_prof = torch_npu.profiler.profile(**profiler_kwargs)
  

def prof_start():
    if torch_npu is None:
        return
    state = get_shared_state()
    if hasattr(state, 'torch_prof'):
        state.torch_prof.start()


def prof_stop():
    if torch_npu is None:
        return
    state = get_shared_state()
    if hasattr(state, 'torch_prof'):
        state.torch_prof.stop()