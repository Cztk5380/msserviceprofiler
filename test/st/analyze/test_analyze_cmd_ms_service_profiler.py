# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import glob
import os
import logging
import json
import shutil
from unittest import TestCase

import pytest
from jsonschema import validate, ValidationError

from ...st.utils import execute_cmd


def check_chrome_tracing_valid(trace_view_json):
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
                        "ts": {"type": "number"},  # 时间戳，单位为微秒
                        "dur": {"type": "number", "minimum": 0},  # 持续时间，适用于 X 类型事件
                        "pid": {"type": "integer"},  # 进程 ID
                        "tid": {"type": "string"},  # 线程 ID
                        "id": {"type": "string"},  # 时间线事件的 ID
                        "cat": {"type": "string"},  # 分类
                        "args": {
                            "type": "object",
                            "additionalProperties": True  # args 可以是任意键值对
                        }
                    },
                    "required": ["name", "ph", "pid", "tid"],  # 必需字段
                    "additionalProperties": False  # 防止额外字段
                }
            }
        },
        "required": ["traceEvents"],  # 必需字段
        "additionalProperties": False  # 防止额外字段
    }

    with open(trace_view_json) as f:
        data = json.load(f)

    # 校验 JSON 数据
    try:
        # 校验 JSON 数据是否符合 schema
        validate(instance=data, schema=schema)
        return True
    except ValidationError as e:
        logging.error(f"JSON validation failed: {e.message}")
        return False


class TestAnalyzeCmd(TestCase):
    ST_DATA_PATH = os.getenv("MS_SERVICE_PROFILER", "/data/ms_service_profiler")
    INPUT_PATH = os.path.join(ST_DATA_PATH, "input/analyze/1230-1148-100Req")
    OUTPUT_PATH = os.path.join(ST_DATA_PATH, "output/analyze")
    COMMAND_SUCCESS = 0
    ANALYZE_PROFILER = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")),
                                    "ms_service_profiler/analyze.py")

    def setup_class(self):
        os.makedirs(self.OUTPUT_PATH, mode=0o750)

    def teardown_class(self):
        shutil.rmtree(self.OUTPUT_PATH)

    def test_profiler(self):
        cmd = ["python", self.ANALYZE_PROFILER, "--input_path", self.INPUT_PATH, "--output_path", self.OUTPUT_PATH]
        if execute_cmd(cmd) != self.COMMAND_SUCCESS or not os.path.exists(self.OUTPUT_PATH):
            self.assertFalse(True, msg="enable ms service profiler analyze task failed.")
        # 校验输出文件是否存在
        db_file = glob.glob(f"{self.OUTPUT_PATH}/*.db")
        csv_file = glob.glob(f"{self.OUTPUT_PATH}/*.csv")
        trace_view_json = glob.glob(f"{self.OUTPUT_PATH}/chrome_tracing.json")[0]

        self.assertEqual(len(db_file), 1, msg="The number of db files is incorrect.")
        self.assertEqual(len(csv_file), 3, msg="The number of csv files is incorrect.")
        if not os.path.exists(trace_view_json):
            self.fail("trace_view.json does not exist")
        pytest.assume(check_chrome_tracing_valid(trace_view_json) is True)
