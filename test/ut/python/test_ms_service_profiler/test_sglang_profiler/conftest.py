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
import importlib
from unittest.mock import patch
import warnings

import pytest


# 确保 handlers 包已加载（reload 子模块前父包必须在 sys.modules 中）
@pytest.fixture(scope="session")
def ensure_handlers_package_loaded():
    importlib.import_module("ms_service_profiler.patcher.sglang.handlers")
    yield


# 会话级 fixture，只对当前目录的测试应用 mock
@pytest.fixture(autouse=True, scope="session")
def mock_profiler_module(ensure_handlers_package_loaded):
    # 使用 patch 而不是替换整个模块
    from .fake_ms_service_profiler import Profiler, Level
    
    # 创建全局的 patch 对象 - 注意使用正确的模块路径
    profiler_patch = patch('ms_service_profiler.Profiler', Profiler)
    level_patch = patch('ms_service_profiler.Level', Level)
    
    # 启动 patch
    profiler_patch.start()
    level_patch.start()

    # 重新加载相关模块确保使用 mock
    modules_to_reload = [
        "ms_service_profiler.patcher.sglang.handlers.scheduler_handlers",
        "ms_service_profiler.patcher.sglang.handlers.request_handlers",
        "ms_service_profiler.patcher.sglang.handlers.model_handlers",
    ]

    for module_name in modules_to_reload:
        importlib.import_module(module_name)

    for module_name in modules_to_reload:
        try:
            importlib.reload(sys.modules[module_name])
        except ImportError as e:
            warnings.warn(f"Failed to reload {module_name}: {e}", RuntimeWarning)
    
    yield
    
    # 停止 patch
    level_patch.stop()
    profiler_patch.stop()

    # 重新加载模块以恢复原始状态（reload 前确保父包在 sys.modules）
    try:
        importlib.import_module("ms_service_profiler.patcher.sglang.handlers")
    except ImportError:
        pass
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            try:
                importlib.reload(sys.modules[module_name])
            except ImportError as e:
                warnings.warn(f"Failed to reload {module_name}: {e}", RuntimeWarning)


# 在每个测试函数前重置 Profiler
@pytest.fixture(autouse=True)
def reset_profiler():
    from .fake_ms_service_profiler import Profiler
    Profiler.reset()
    yield
    Profiler.reset()

