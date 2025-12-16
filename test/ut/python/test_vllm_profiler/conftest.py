# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
        "ms_service_profiler.vllm_profiler.vllm_v0.batch_hookers",
        "ms_service_profiler.vllm_profiler.vllm_v1.batch_hookers",
        "ms_service_profiler.vllm_profiler.vllm_v0.model_hookers",
        "ms_service_profiler.vllm_profiler.vllm_v1.model_hookers",
        "ms_service_profiler.vllm_profiler.vllm_v0.kvcache_hookers",
        "ms_service_profiler.vllm_profiler.vllm_v1.kvcache_hookers",
        "ms_service_profiler.vllm_profiler.vllm_v0.request_hookers",
        "ms_service_profiler.vllm_profiler.vllm_v1.request_hookers",
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
    with patch("ms_service_profiler.vllm_profiler.vllm_v1.model_hookers.synchronize"):
        yield
