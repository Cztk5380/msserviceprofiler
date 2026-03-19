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

import os
import sys
import subprocess
from typing import List, Tuple

# SGLang handlers 中 span_start/event 的数据点位名称（ms_service_profiler/patcher/sglang/handlers）
# 注：HitCache 等部分点位为条件触发，若用例未覆盖可从此列表移除
SGLANG_PROF_DATA_POINT_NAMES = [
    "detokenize",
    "tokenize",
    "send_to_scheduler.dispatch",
    "preprocess",
    "forward",
    "sample",
    "processReq",
    "batchFrameworkProcessing",
    "modelExec",
    "postprocess",
    "DecodeEnd",
    "httpRes",
    "httpReq",
    "recvReq",
    "Enqueue",
    "Queue",
    "Dequeue",
    "HitCache",
    # "PrefillEnd", 只有并发场景下会有这个点
    "allocate",
    "free",
]


def check_prof_data_contains_sglang_points(prof_dir: str) -> Tuple[bool, List[str]]:
    """
    使用 grep 检查 prof_data 目录下是否包含 SGLang 数据点位名称。
    遍历完整列表后汇总所有缺失项，打印后返回；不缺少则继续。

    返回:
        (是否全部包含, 缺失的点位名称列表)
    """
    if not os.path.isdir(prof_dir):
        missing = list(SGLANG_PROF_DATA_POINT_NAMES)
        print(f"[ERROR] prof_data 目录不存在或非目录: {prof_dir}", file=sys.stderr)
        print(f"[ERROR] 缺失的数据点位（全部）: {missing}", file=sys.stderr)
        return False, missing
    missing = []
    for name in SGLANG_PROF_DATA_POINT_NAMES:
        try:
            result = subprocess.run(
                ["grep", "-r", "-l", name, prof_dir],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                missing.append(name)
        except (subprocess.TimeoutExpired, OSError):
            missing.append(name)
    if missing:
        print(f"[ERROR] prof_data 目录下缺少以下 SGLang 数据点位（grep 未匹配）: {missing}", file=sys.stderr)
    return len(missing) == 0, missing
