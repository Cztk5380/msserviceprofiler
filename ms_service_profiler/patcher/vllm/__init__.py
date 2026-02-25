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
vLLM 服务分析器入口模块。
"""

from ..core.logger import set_log_level, logger
from .service_patcher import VLLMProfiler
from ...mstx import service_profiler as mstx_profiler

set_log_level("info")

# 创建 vLLM 专用的 Profiler 实例
_vllm_profiler = VLLMProfiler()


def register_service_profiler():
    """初始化 vLLM 服务分析器并注册回调。"""
    # 1. 初始化 profiler
    ok = _vllm_profiler.initialize()
    if not ok:
        return

    # 2. 获取回调函数
    on_start, on_stop = _vllm_profiler.get_callbacks()

    # 3. 注册回调到 mstx
    start_result = mstx_profiler.register_profiler_start_callback(on_start)
    stop_result = mstx_profiler.register_profiler_stop_callback(on_stop)

    on_start_metric, on_stop_metric = _vllm_profiler.get_metric_callbacks()
    mstx_profiler.register_profiler_start_metric_callback(on_start_metric)
    mstx_profiler.register_profiler_stop_metric_callback(on_stop_metric)
    
    # 4. 根据结果处理
    if start_result.is_dynamic and stop_result.is_dynamic:
        logger.info("Successfully registered VLLM profiler callbacks (dynamic mode)")
        logger.info("Hooks will be enabled/disabled automatically by profiler start/stop signals")
    else:
        logger.info("C++ library does not support dynamic callbacks, enabling hooks immediately (legacy mode)")
        _vllm_profiler.enable_hooks()
