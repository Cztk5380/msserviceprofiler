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

import sys
import types
import importlib
from unittest.mock import patch

import pytest


# 会话级 fixture，只对当前目录的测试应用 mock
@pytest.fixture(autouse=True, scope="session")
def mock_profiler_module():
    # 使用 patch 而不是替换整个模块
    from .fake_ms_service_profiler import Profiler, Level
    
    # 创建全局的 patch 对象
    profiler_patch = patch('ms_service_profiler.Profiler', Profiler)
    level_patch = patch('ms_service_profiler.Level', Level)
    
    # 启动 patch
    profiler_patch.start()
    level_patch.start()

    # 重新加载相关模块确保使用 mock
    modules_to_reload = [
        "ms_service_profiler.patcher.vllm.handlers.v0.batch_handlers",
        "ms_service_profiler.patcher.vllm.handlers.v1.batch_handlers",
        "ms_service_profiler.patcher.vllm.handlers.v0.model_handlers",
        "ms_service_profiler.patcher.vllm.handlers.v1.model_handlers",
        "ms_service_profiler.patcher.vllm.handlers.v0.kvcache_handlers",
        "ms_service_profiler.patcher.vllm.handlers.v1.kvcache_handlers",
        "ms_service_profiler.patcher.vllm.handlers.v0.request_handlers",
        "ms_service_profiler.patcher.vllm.handlers.v1.request_handlers",
    ]
    
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
    
    yield
    
    # 停止 patch
    level_patch.stop()
    profiler_patch.stop()
    
    # 重新加载模块以恢复原始状态
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])


# 在每个测试函数前重置 Profiler
@pytest.fixture(autouse=True)
def reset_profiler():
    from .fake_ms_service_profiler import Profiler
    Profiler.reset()
    yield
    Profiler.reset()


@pytest.fixture(autouse=True)
def patch_model_hookers_synchronize():
    with patch("ms_service_profiler.patcher.vllm.handlers.v1.model_handlers.synchronize"):
        yield
