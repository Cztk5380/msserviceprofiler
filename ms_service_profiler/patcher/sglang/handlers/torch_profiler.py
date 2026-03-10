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

import json
import torch
import torch_npu
from ms_service_profiler.mstx import service_profiler
from ms_service_profiler.profiler import Level
from ms_service_profiler.utils.log import logger
from ms_service_profiler.patcher.sglang import get_shared_state


def torch_profiler_register():
    step_num = service_profiler.get_torch_prof_step_num()

    if step_num and step_num > 0:
        return
    
    if service_profiler.is_torch_profiler_register():
        prof_build()
        service_profiler.register_profiler_start_callback(prof_start)
        service_profiler.register_profiler_stop_callback(prof_stop)
    
    
def prof_build():
    global torch_prof
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
    state = get_shared_state()
    torch.npu.set_device(state._rank)
    state.torch_prof.start()


def prof_stop():
    state = get_shared_state()
    state.torch_prof.stop()