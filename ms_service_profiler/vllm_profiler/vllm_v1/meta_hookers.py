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
from .utils import SharedHookState, create_state_getter


class MetaCollectionState(SharedHookState):
    def __init__(self):
        super().__init__()
        self.has_collected = False  # 添加状态标记属性


# 线程本地存储获取器（每文件独立线程状态）
_get_state = create_state_getter(MetaCollectionState)


@vllm_hook(("vllm.v1.engine.core", "DPEngineCoreProc.add_request"), min_version="0.9.1")
def init_data_parallel(original_func, this, vllm_config, *args, **kwargs):
    ret = original_func(this, vllm_config, *args, **kwargs)

    state = _get_state()

    # 若此进程还没采集过dpRankId,则添加meta数据
    if not state.has_collected:
        Profiler(Level.INFO).add_meta_info("dpRankId", this.dp_rank)
        state.has_collected = True  # 更新状态类中的属性

    return ret
