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
ms_service_metric.core.hook - Hook 相关模块

提供 Hook 链管理、Hook 辅助工具和字节码注入功能。
"""

from ms_service_metric.core.hook.hook_chain import HookChain, HookNode, NO_RESULT
from ms_service_metric.core.hook.hook_helper import HookHelper
from ms_service_metric.core.hook.inject import inject_function

__all__ = [
    "HookChain",
    "HookNode",
    "NO_RESULT",
    "HookHelper",
    "inject_function",
]
