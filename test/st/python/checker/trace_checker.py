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
import os
from jsonschema import validate
from pytest_check import check


def check_chrome_tracing(output_path):
    trace_file_path = f"{output_path}/chrome_tracing.json"
    with check(f"check[{trace_file_path}]"):
        assert os.path.exists(trace_file_path)

        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "ph": {"type": "string", "enum": ["X", "I", "C", "M", "s", "f", "t"]},
                    "ts": {"type": ["number", "string"], "pattern": "^\\d+(\\.\\d+)?$"},  # 时间戳，单位为微秒
                    "dur": {"type": "number", "minimum": 0},  # 持续时间，适用于 X 类型事件
                    "pid": {"type": "integer"},  # 进程 ID
                    "tid": {"type": ["string", "integer"]},
                    "id": {"type": "string"},  # 时间线事件的 ID
                    "cat": {"type": "string"},  # 分类
                    "args": {"type": "object", "additionalProperties": True},  # args 可以是任意键值对
                },
                "required": ["name", "ph", "pid"],  # 必需字段
                "additionalProperties": True,
            }
        }

        with open(trace_file_path) as f:
            data = json.load(f)

        validate(instance=data, schema=schema)
