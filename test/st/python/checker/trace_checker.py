import json
import os
from jsonschema import validate
from pytest_check import check


def check_chrome_tracing(output_path):
    trace_file_path = f"{output_path}/chrome_tracing.json"
    with check(f"check[{trace_file_path}]"):
        assert os.path.exists(trace_file_path)

        schema = {
            "type": "object",
            "properties": {
                "traceEvents": {
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
                        "additionalProperties": False,  # 防止额外字段
                    },
                }
            },
            "required": ["traceEvents"],  # 必需字段
            "additionalProperties": False,  # 防止额外字段
        }
        with open(trace_file_path) as f:
            data = json.load(f)

        validate(instance=data, schema=schema)
