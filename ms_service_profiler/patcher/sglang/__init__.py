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

"""
SGLang 服务分析器入口模块。
"""

from ..core.logger import set_log_level, logger
from .service_patcher import SGLangPatcher
from ...mstx import service_profiler as mstx_profiler
from ms_service_profiler.patcher.core.utils import get_shared_state


set_log_level("info")  # Default is info, put here for user changes


# 创建SGLang专用的Profiler实例
_sglang_patcher = SGLangPatcher()

def register_service_profiler():
    """初始化SGLang服务分析器。"""
    # 1. 初始化 profiler
    ok = _sglang_patcher.initialize()
    if not ok:
        return
    
    # 2. 获取回调函数
    on_start, on_stop = _sglang_patcher.get_callbacks()

    # 3. 注册回调到 mstx
    start_result = mstx_profiler.register_profiler_start_callback(on_start)
    stop_result = mstx_profiler.register_profiler_stop_callback(on_stop)
    
    # 4. 根据结果处理
    if start_result.is_dynamic and stop_result.is_dynamic:
        logger.info("Successfully registered SGLang profiler callbacks (dynamic mode)")
        logger.info("Hooks will be enabled/disabled automatically by profiler start/stop signals")
    else:
        logger.info("C++ library does not support dynamic callbacks, enabling hooks immediately (legacy mode)")
        _sglang_patcher.enable_hooks()
    
    patch_model_runner_with_torch_profiler()
    patch_model_runner_init_torch_distributed()


def patch_model_runner_with_torch_profiler():
    import sglang.srt.model_executor.model_runner
    from sglang.srt.model_executor.model_runner import ModelRunner
    from ms_service_profiler.patcher.sglang.handlers.torch_profiler import torch_profiler_register

    original_load_model = ModelRunner.load_model

    def new_load_model(self, *args, **kwargs):
        result = original_load_model(self, *args, **kwargs)
        torch_profiler_register()
        return result

    ModelRunner.load_model = new_load_model


def patch_model_runner_init_torch_distributed():

    import sglang.srt.model_executor.model_runner
    from sglang.srt.model_executor.model_runner import ModelRunner
    state = get_shared_state()
    original_init_torch_distributed = ModelRunner.init_torch_distributed

    def new_init_torch_distributed(self, *args, **kwargs):

        result = original_init_torch_distributed(self, *args, **kwargs)
        with state._lock:
            state._rank = self.gpu_id
        return result

    ModelRunner.init_torch_distributed = new_init_torch_distributed