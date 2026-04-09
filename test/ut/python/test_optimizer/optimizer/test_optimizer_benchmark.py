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
import shutil
import re
from pathlib import Path
import unittest
import shutil
from unittest.mock import patch, MagicMock, mock_open
import csv
import pandas as pd
import pytest
from msguard import GlobalConfig
from ms_serviceparam_optimizer.config.config import PerformanceIndex, get_settings, AisBenchConfig, \
    OptimizerConfigField
from ms_serviceparam_optimizer.optimizer.plugins.benchmark import parse_result, AisBench, VllmBenchMark


settings = get_settings()


class TestParseResult(unittest.TestCase):
    def test_string_with_ms(self):
        # 测试输入为字符串，且单位为ms的情况
        self.assertAlmostEqual(parse_result("123 ms"), 0.123)

    def test_string_with_us(self):
        # 测试输入为字符串，且单位为us的情况
        self.assertAlmostEqual(parse_result("456 us"), 0.000456)

    def test_string_with_other_unit(self):
        # 测试输入为字符串，但单位不是ms或us的情况
        self.assertAlmostEqual(parse_result("789 s"), 789.0)

    def test_string_without_unit(self):
        # 测试输入为字符串，但没有单位的情况
        self.assertAlmostEqual(parse_result("1010"), 1010.0)


@pytest.fixture
def results_per_request_file(tmpdir):
    file_path = Path(tmpdir).joinpath("results_per_request_202507181613.json")
    data = {
        "1": {
            "input_len": 1735,
            "output_len": 1,
            "prefill_bsz": 4,
            "decode_bsz": [],
            "req_latency": 13058.372889645398,
            "latency": [
                13058.23168065399
            ],
            "queue_latency": [
                12598012
            ],
            "input_data": "", "output": ""
        },
        "2": {
            "prefill_bsz": 4,
            "decode_bsz": [],
            "req_latency": 15173.639830201864,
            "latency": [
                15173.517209477723
            ],
            "queue_latency": [
                14708480
            ],
            "input_data": "", "output": ""
        },
        "3": {
            "input_len": 1777,
            "output_len": 3,
            "prefill_bsz": 4,
            "decode_bsz": [
                157,
                157
            ],
            "req_latency": 15456.984990276396,
            "latency": [
                15178.787489421666,
                208.4683496505022,
                69.54238004982471
            ],
            "queue_latency": [
                14711475,
                127888,
                3709
            ],
            "input_data": "", "output": "\t\tif ("
        },
        "4": {
            "input_len": 1770,
            "output_len": 3,
            "prefill_bsz": 4,
            "decode_bsz": [
                157,
                157
            ],
            "req_latency": 15481.421849690378,
            "latency": [
                14745.695400051773,
                670.0493693351746,
                64.66158013790846
            ],
            "queue_latency": [
                14280800,
                584221,
                3686
            ],
            "input_data": "", "output": "Passage "
        },
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return file_path


class TestBenchMarkGetPerformanceIndex(unittest.TestCase):
    @patch("ms_serviceparam_optimizer.config.custom_command.shutil.which")
    def setUp(self, mock_which):
        # 创建一个模拟的 benchmark_config 对象
        self.mock_benchmark_config = MagicMock()
        mock_which.return_value = "/usr/local/bin/vllm"
        # 配置 command 属性，确保 others 是字符串而不是 MagicMock
        self.mock_benchmark_config.command = MagicMock()
        self.mock_benchmark_config.command.serving = ""
        self.mock_benchmark_config.command.backend = "vllm"
        self.mock_benchmark_config.command.host = ""
        self.mock_benchmark_config.command.port = ""
        self.mock_benchmark_config.command.model = ""
        self.mock_benchmark_config.command.served_model_name = ""
        self.mock_benchmark_config.command.dataset_name = ""
        self.mock_benchmark_config.command.dataset_path = ""
        self.mock_benchmark_config.command.num_prompts = 0
        self.mock_benchmark_config.command.result_dir = ""
        self.mock_benchmark_config.command.others = ""  # 关键：设置为字符串而不是 MagicMock
        # 创建测试对象并传递 benchmark_config
        self.benchmark = VllmBenchMark(self.mock_benchmark_config)
        
        # 设置 command 属性
        self.benchmark.config.command = MagicMock()
        self.test_dir = Path("test_dir")
        self.benchmark.config.command.result_dir = self.test_dir
        self.test_dir.mkdir(exist_ok=True)
        self.json_path = self.test_dir / "result.json"
        json_data = {
            "output_throughput": 2000.0,
            "mean_ttft_ms": 600.0,
            "mean_tpot_ms": 140.0,
            "num_prompts": 10,
            "completed": 10,
            "request_throughput": 4.0
        }
        with open(self.json_path, 'w') as f:
            json.dump(json_data, f)

    
    def tearDown(self):
        # 清理临时目录
        shutil.rmtree(self.test_dir)
    
    def test_get_performance_index_normal(self):
        GlobalConfig.custom_return = True
        """测试正常情况下的get_performance_index方法"""
        
        # 调用方法
        result = self.benchmark.get_performance_index()
        
        # 验证结果
        self.assertIsInstance(result, PerformanceIndex)
        self.assertEqual(result.generate_speed, 2000.0)
        self.assertEqual(result.time_to_first_token, 0.6)  
        self.assertEqual(result.time_per_output_token, 0.14)
        self.assertEqual(result.success_rate, 1.0)
        self.assertEqual(result.throughput, 4.0)
    
        GlobalConfig.reset()