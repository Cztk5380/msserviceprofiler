# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from ms_service_profiler.exporters.exporter_summary import (
    is_contained_vaild_iter_info,
    process_batch_record,
    calculate_statistics,
    convert_map_to_dataframe,
    process_req_record,
    process_rid_token_list,
    calculate_request_metrics,
    gen_exporter_results,
    process_each_record,  # 新增导入，用于测试该函数
    save_dataframe_to_csv  # 新增导入，用于测试该函数
)


class TestExporterSummaryFunctions(unittest.TestCase):
    def setUp(self):
        # 公共测试数据
        self.sample_batch_map = {}
        self.sample_req_map = {'1001': {'token_id': {}}}
        self.valid_rid_list = [1, 2]
        self.valid_iter_list = [0, 1]
        self.req_map = {}

    def test_is_contained_valid_iter_info_normal(self):
        """测试正常情况下的迭代信息验证"""
        self.assertTrue(
            is_contained_vaild_iter_info(self.valid_rid_list, self.valid_iter_list),
            "应验证有效迭代信息"
        )

    def test_is_contained_valid_iter_info_edge_cases(self):
        """测试边界情况下的迭代信息验证"""
        # 空rid列表
        self.assertFalse(
            is_contained_vaild_iter_info([], self.valid_iter_list),
            "空rid列表应返回False"
        )
        # 长度不一致
        self.assertFalse(
            is_contained_vaild_iter_info([1], self.valid_iter_list),
            "长度不一致应返回False"
        )
        # 新增：测试 rid_list 为 None 的情况
        self.assertFalse(
            is_contained_vaild_iter_info(None, self.valid_iter_list),
            "rid_list 为 None 应返回 False"
        )
        # 新增：测试 token_id_list 为 None 的情况
        self.assertFalse(
            is_contained_vaild_iter_info(self.valid_rid_list, None),
            "token_id_list 为 None 应返回 False"
        )

    def test_process_batch_record_multiple_types(self):
        prefill_record = {
            'batch_type': 'Prefill',
            'rid_list': [1001],
            'batch_size': 8,
            'during_time': 1_500_000  # 1.5秒
        }
        process_batch_record(self.sample_batch_map, prefill_record)
        prefill_key = f"prefill_{str(prefill_record['rid_list'])}"
        self.assertTrue(prefill_key in self.sample_batch_map, f"键 {prefill_key} 未在 sample_batch_map 中找到")
        self.assertEqual(self.sample_batch_map[prefill_key]['prefill_batch_num'], 8)
        self.assertAlmostEqual(self.sample_batch_map[prefill_key]['prefill_exec_time (ms)'], 1500.0)
        # 测试Decode类型
        decode_record = {
            'batch_type': 'Decode',
            'rid_list': [1002],
            'batch_size': 4,
            'during_time': 500_000  # 0.5秒
        }
        process_batch_record(self.sample_batch_map, decode_record)
        decode_key = f"decode_{str(decode_record['rid_list'])}"
        self.assertTrue(decode_key in self.sample_batch_map, f"键 {decode_key} 未在 sample_batch_map 中找到")
        self.assertEqual(self.sample_batch_map[decode_key]['decode_batch_num'], 4)
        self.assertAlmostEqual(self.sample_batch_map[decode_key]['decode_exec_time (ms)'], 500.0)
        unknown_record = {
            'batch_type': 'Unknown',
            'rid_list': [1003],
            'batch_size': 2,
            'during_time': 200_000
        }
        process_batch_record(self.sample_batch_map, unknown_record)
        self.assertEqual(len(self.sample_batch_map), 2, "未知 batch_type 不应添加新项")

    def test_calculate_statistics_comprehensive(self):
        """测试全面的统计计算"""
        test_cases = [
            ([10, 20, 30], {'avg': 20, 'p50': 20, 'p90': 28, 'p99': 29.8}),
            ([5], {'avg': 5, 'p50': 5, 'p90': 5, 'p99': 5}),
            ([], {'avg': np.nan, 'p50': np.nan, 'p90': np.nan, 'p99': np.nan})
        ]

        for data, expected in test_cases:
            with self.subTest(data=data):
                result = calculate_statistics(data)
                if data:
                    self.assertAlmostEqual(result['avg'], expected['avg'], places=1)
                    self.assertAlmostEqual(result['p50'], expected['p50'], places=1)
                    self.assertAlmostEqual(result['p90'], expected['p90'], places=1)
                else:
                    self.assertTrue(np.isnan(result['avg']))

        # 新增：测试包含非数字元素的情况
        non_numeric_data = [10, 'a', 30]
        result = calculate_statistics(non_numeric_data)
        self.assertTrue(np.isnan(result['avg']), "包含非数字元素应返回 nan")

    def test_convert_map_to_dataframe_detailed(self):
        """测试详细的DataFrame转换"""
        map_data = {
            "latency": {"avg": 15.5, "max": 30, "min": 5, "p50": 15, "p90": 27, "p99": 29},
            "throughput": {"avg": 100, "max": 200, "min": 50, "p50": 100, "p90": 180, "p99": 198}
        }
        df = convert_map_to_dataframe(map_data, include_stats=1)

        # 验证列名和索引
        self.assertListEqual(df.index.tolist(), [0, 1])
        self.assertListEqual(df.columns.tolist(), ['Metric', 'average', 'max', 'min', 'P50', 'P90', 'P99'])

        # 验证数值精度
        self.assertAlmostEqual(df.loc[0, 'average'], 15.5)
        self.assertEqual(df.loc[1, 'max'], 200)

        # 新增：测试 include_stats = 0 的情况
        map_data_speed = {
            "generate_token_speed (token/s)": 123.456789
        }
        df_speed = convert_map_to_dataframe(map_data_speed, include_stats=0)
        self.assertListEqual(df_speed.columns.tolist(), ['Metric', 'value'])
        self.assertEqual(df_speed.loc[0, 'Metric'], "generate_token_speed (token/s)")
        self.assertEqual(df_speed.loc[0, 'value'], "123.45678900")

    def test_full_request_lifecycle_metrics(self):
        # 构建完整的请求记录
        req_map = {
            '1001': {
                'httpReq_start': 1_630_000_000_000,
                'httpRes_end': 1_630_000_002_000,
                'first_token_latency': 50_000,
                'exec_time': 100_000,
                'input_token_num': 10,
                'generated_token_num': 20,
                'token_id': {
                    0: 1_630_000_000_500,
                    1: 1_630_000_001_000
                },
                'req_waiting_time': 10_000,
                'req_pending_time': 20_000
            }
        }

        req_view, total_map = calculate_request_metrics(req_map)

        # 验证单个请求指标
        self.assertEqual(len(req_view), 1)
        request_metrics = req_view[0]

        self.assertEqual(request_metrics['req_id'], '1001')
        self.assertAlmostEqual(request_metrics['exec_time'], 100.0)
        self.assertAlmostEqual(request_metrics['first_token_latency'], 50.0)
        self.assertEqual(request_metrics['subsequent_token_latency'], [0.5])
        self.assertEqual(request_metrics['input_token_num'], 10)
        self.assertEqual(request_metrics['generated_token_num'], 20)

        # 验证聚合指标
        self.assertEqual(total_map['total_input_token_num'], 10)
        self.assertEqual(total_map['total_generated_token_num'], 20)
        # 修正原代码中速度计算错误，这里根据实际计算逻辑修改预期值
        total_exec_time = (1_630_000_002_000 - 1_630_000_000_000) / 1000000
        generate_token_speed = 20 / total_exec_time
        generate_all_token_speed = (10 + 20) / total_exec_time
        self.assertAlmostEqual(total_map['generate_token_speed (token/s)'], generate_token_speed, places=3)
        self.assertAlmostEqual(total_map['generate_all_token_speed (token/s)'], generate_all_token_speed, places=3)

    @patch('logging.Logger.warning')
    def test_missing_http_components(self, mock_warning):
        """测试缺失HTTP组件的情况"""
        incomplete_data = pd.DataFrame([{
            'name': 'httpRes',
            'rid': '1001',
            'end_time': 1_630_000_002_000
        }])

        gen_exporter_results(incomplete_data)
        mock_warning.assert_called_with("Missing httpReq for httpRes with rid=1001.")

    def test_token_throughput_calculation(self):
        """测试Token吞吐量计算"""
        http_req_start = 1735124805384149
        token_id_0 = 1735124805784100
        token_id_1 = 1735124806061010
        http_res_end = 1735124815365194
        req_map = {
            "1": {
                "httpReq_start": http_req_start,
                "token_id": {
                    "0": token_id_0,
                    "1": token_id_1,
                },
                "req_waiting_time": 0.0,
                "req_pending_time": 0.0,
                "req_exec_time": 1735124805384149.2,
                "input_token_num": 4.0,
                "first_token_latency": 416819.0,
                "exec_time": 8915139.0,
                "generated_token_num": 250.0,
                "httpRes_end": http_res_end
            }
        }

        _, total_map = calculate_request_metrics(req_map)
        self.assertAlmostEqual(total_map['total_input_token_num'], 4.0)
        self.assertAlmostEqual(total_map['total_generated_token_num'], 250.0)
        total_exec_time = (http_res_end - http_req_start) / 1000000
        generate_token_speed = 250 / total_exec_time
        generate_all_token_speed = (4 + 250) / total_exec_time

        generate_token_speed = round(generate_token_speed, 4)
        generate_all_token_speed = round(generate_all_token_speed, 4)

        self.assertAlmostEqual(total_map['generate_token_speed (token/s)'], generate_token_speed, places=3)
        self.assertAlmostEqual(total_map['generate_all_token_speed (token/s)'], generate_all_token_speed, places=3)

    def test_process_each_record(self):
        record = {
            'name': 'httpReq',
            'rid': '1002',
            'start_time': 1_630_000_000_000
        }
        process_each_record(self.sample_req_map, self.sample_batch_map, record)
        self.assertIn('1002', self.sample_req_map, "请求记录应被处理")

    @patch('pandas.DataFrame.to_csv')
    @patch('os.chmod')
    def test_save_dataframe_to_csv(self, mock_chmod, mock_to_csv):
        map_data = {
            "latency": {"avg": 15.5, "max": 30, "min": 5, "p50": 15, "p90": 27, "p99": 29}
        }
        output = "/tmp/test_output"
        file_name = "test.csv"
        save_dataframe_to_csv(map_data, output, file_name)
        mock_to_csv.assert_called_once()
        mock_chmod.assert_called_once()

    def test_process_req_record(self):
        # 构建 httpReq 记录
        http_req_record = {
            'name': 'httpReq',
            'rid': '0',
            'start_time': 1739276837290586.5
        }
        process_req_record(self.req_map, http_req_record)
        # 构建包含 token_id 信息的记录
        token_id_record = {
            'name': 'modelExec',
            'rid': '0',
            'rid_list': ['0'],
            'token_id_list': ['0'],
            'end_time': 1739276837517605.2,
            'during_time': 142208.75
        }
        process_req_record(self.req_map, token_id_record)
        # 构建 httpRes 记录
        http_res_record = {
            'name': 'httpRes',
            'rid': '0',
            'end_time': 1739276841538271.0,
            'replyTokenSize=': 250.0
        }
        process_req_record(self.req_map, http_res_record)
        # 构建输入 Token 数量记录
        input_token_record = {
            'name': 'modelExec',
            'rid': '0',
            'recvTokenSize=': 4.0
        }
        process_req_record(self.req_map, input_token_record)
        # 验证 req_map 的内容
        self.assertEqual(len(self.req_map), 1)
        self.assertEqual(self.req_map['0']['httpReq_start'], 1739276837290586.5)
        self.assertEqual(self.req_map['0']['token_id']['0'], 1739276837517605.2)
        self.assertTrue(self.req_map['0']['is_complete'], True)
        self.assertEqual(self.req_map['0']['input_token_num'], 4.0)
        self.assertEqual(self.req_map['0']['generated_token_num'], 250.0)
        self.assertEqual(self.req_map['0']['httpRes_end'], 1739276841538271.0)


if __name__ == '__main__':
    unittest.main()