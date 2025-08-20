# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import MagicMock

import pandas as pd

from ms_service_profiler.processor.processor_res import ProcessorRes


class TestProcessorRes(unittest.TestCase):

    def setUp(self):
        self.processor = ProcessorRes()

    def test_name(self):
        # 测试 name 属性
        expected_name = "ProcessorRes"
        self.assertEqual(self.processor.name, expected_name)

    def test_parse_process_info_empty_df(self):
        # 测试空的 DataFrame
        data_df = None
        index = 0
        result = self.processor.parse_process_info(data_df, index)
        self.assertEqual(result, {})

    def test_parse_process_info_normal_forward(self):
        # 测试包含 "forward" 的 DataFrame
        data = {
            "hostname": ["host1", "host2"],
            "pid": [1001, 1002],
            "name": ["forward", "other"],
            "ppid": [None, 1000],
            "deviceid": [1, None]
        }
        data_df = pd.DataFrame(data)
        index = 0
        result = self.processor.parse_process_info(data_df, index)
        expected_result = {
            "hostname": "host2",
            "pid": "1002",
            "index": index,
            "ppid": 1000.0,
            "device_id": 1.0,
            "is_forward": True,  # 因为存在 "forward"，所以 is_forward 为 True
            "df": data_df
        }
        self.assertEqual(result, expected_result)

    def test_parse_process_info_normal_no_forward(self):
        # 测试不包含 "forward" 的 DataFrame
        data = {
            "hostname": ["host1", "host2"],
            "pid": [1001, 1002],
            "name": ["other1", "other2"],
            "ppid": [None, 1000],
            "deviceid": [1, None]
        }
        data_df = pd.DataFrame(data)
        index = 0
        result = self.processor.parse_process_info(data_df, index)
        expected_result = {
            "hostname": "host2",
            "pid": "1002",
            "index": index,
            "ppid": 1000.0,
            "device_id": 1.0,
            "is_forward": False,  # 因为不存在 "forward"，所以 is_forward 为 False
            "df": data_df
        }
        self.assertEqual(result, expected_result)

    def test_parse_process_info_missing_columns(self):
        # 测试缺少某些列的 DataFrame
        data = {
            "hostname": ["host1"],
            "pid": [1001],
            "name": ["forward"]
        }
        data_df = pd.DataFrame(data)
        index = 0
        result = self.processor.parse_process_info(data_df, index)
        expected_result = {
            "hostname": "host1",
            "pid": "1001",
            "index": index,
            "ppid": None,
            "device_id": None,
            "is_forward": True,
            "df": data_df
        }
        self.assertEqual(result, expected_result)

    def test_parse_process_info_with_ppid(self):
        # 测试包含 ppid 的 DataFrame
        data = {
            "hostname": ["host1", "host2"],
            "pid": [1001, 1002],
            "name": ["forward", "other"],
            "ppid": [1000, 1001],  # 包含有效的 ppid
            "deviceid": [1, None]
        }
        data_df = pd.DataFrame(data)
        index = 0
        result = self.processor.parse_process_info(data_df, index)
        expected_result = {
            "hostname": "host2",
            "pid": "1002",
            "index": index,
            "ppid": 1001,  # 获取最后一个非空的 ppid
            "device_id": 1.0,
            "is_forward": True,
            "df": data_df
        }
        self.assertEqual(result, expected_result)

    def test_mapping_rid_list(self):
        # 测试映射 rid 为列表的情况
        rid = [1, 2, 3]
        rid_map = {'1': "a", '2': "b", '3': "c"}
        result = self.processor.mapping_rid(rid, rid_map)
        expected_result = ["a", "b", "c"]
        self.assertEqual(result, expected_result)

    def test_mapping_rid_dict(self):
        # 测试映射 rid 为字典的情况
        rid = {"rid": 1}
        rid_map = {'1': "a"}
        result = self.processor.mapping_rid(rid, rid_map)
        expected_result = {"rid": "a"}
        self.assertEqual(result, expected_result)

    def test_mapping_rid_other(self):
        # 测试映射 rid 为其他类型的情况
        rid = 1
        rid_map = {'1': "a"}
        result = self.processor.mapping_rid(rid, rid_map)
        expected_result = "a"
        self.assertEqual(result, expected_result)

    def test_mapping_rid_dict_with_rid_key(self):
        # 测试 rid 为字典且包含 'rid' 键的情况
        rid = {"rid": 1}
        rid_map = {'1': "a"}
        result = self.processor.mapping_rid(rid, rid_map)
        expected_result = {"rid": "a"}
        self.assertEqual(result, expected_result)

    def test_parse_empty_data(self):
        # 测试空的输入数据
        data = dict()
        result = self.processor.parse(data, dict(), list())
        self.assertEqual(result, dict())

    def test_parse_normal(self):
        # 测试正常的输入数据
        data = [
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host1", "host2"],
                    "pid": [1001, 1002],
                    "name": ["forward", "other"],
                    "ppid": [None, 1000],
                    "deviceid": [1, None],
                    "from": [None, 1],
                    "to": [None, 2]
                })
            },
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host3"],
                    "pid": [1003],
                    "name": ["forward"],
                    "ppid": [1002],
                    "deviceid": [None],
                    "from": [None],
                    "to": [None]
                })
            }
        ]
        result = self.processor.parse(data[1], dict(), list())
        self.assertIsNotNone(result)

    def test_parse_missing_columns(self):
        # 测试缺少某些列的输入数据
        data = [
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host1"],
                    "pid": [1001],
                    "name": ["forward"]
                })
            }
        ]
        result = self.processor.parse(data[0], dict(), list())
        self.assertIsNotNone(result)

    def test_parse_with_non_forward_process(self):
        # 测试包含非 forward 进程的情况
        data = [
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host1"],
                    "pid": [1001],
                    "name": ["other"],
                    "ppid": [None],
                    "deviceid": [1],
                    "from": [1],
                    "to": [2],
                    "rid": [10]
                })
            },
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host2"],
                    "pid": [1002],
                    "name": ["forward"],
                    "ppid": [1001],
                    "deviceid": [None],
                    "from": [None],
                    "to": [None],
                    "rid": [20]
                })
            }
        ]

        result = self.processor.parse(data[0], dict(), list())
        # 检查结果
        self.assertIsNotNone(result)

        # 检查第一个进程（非 forward 进程）
        first_process = result
        self.assertIn("tx_data_df", first_process)
        first_df = first_process["tx_data_df"]
        self.assertTrue(first_df.empty)  # from 列不为空的数据被移除

        result = self.processor.parse(data[1], dict(), list())
        # 检查第二个进程（forward 进程）
        second_process = result
        self.assertIn("tx_data_df", second_process)
        second_df = second_process["tx_data_df"]
        self.assertEqual(second_df.iloc[0]["rid"], '20')  # rid 应该被正确映射

    def test_parse_with_non_forward_process_empty_df(self):
        # 测试非 forward 进程的 DataFrame 为空的情况
        data = [
            {
                "tx_data_df": None  # 空的 DataFrame
            },
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host2"],
                    "pid": [1002],
                    "name": ["forward"],
                    "ppid": [1001],
                    "deviceid": [None],
                    "from": [None],
                    "to": [None],
                    "rid": [20]
                })
            }
        ]

        result = self.processor.parse(data[0], dict(), list())
        self.assertIsNotNone(result)
        # 检查第一个进程（非 forward 进程）
        first_process = result
        self.assertIn("tx_data_df", first_process)
        self.assertIsNone(first_process["tx_data_df"])  # 空的 DataFrame 应该保持为空

        result = self.processor.parse(data[1], dict(), list())
        self.assertIsNotNone(result)
        # 检查第二个进程（forward 进程）
        second_process = result
        self.assertIn("tx_data_df", second_process)
        second_df = second_process["tx_data_df"]
        self.assertEqual(second_df.iloc[0]["rid"], '20')  # rid 应该被正确映射

    def test_parse_with_non_forward_process_missing_columns(self):
        # 测试非 forward 进程的 DataFrame 缺少 from 或 to 列的情况
        data = [
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host1"],
                    "pid": [1001],
                    "name": ["other"],
                    "ppid": [None],
                    "deviceid": [1],
                    "rid": [10]  # 缺少 from 和 to 列
                })
            },
            {
                "tx_data_df": pd.DataFrame({
                    "hostname": ["host2"],
                    "pid": [1002],
                    "name": ["forward"],
                    "ppid": [1001],
                    "deviceid": [None],
                    "from": [None],
                    "to": [None],
                    "rid": [20]
                })
            }
        ]

        result = self.processor.parse(data[0], dict(), list())

        # 检查结果
        self.assertIsNotNone(result)
        # 检查第一个进程（非 forward 进程）
        first_process = result
        self.assertIn("tx_data_df", first_process)
        self.assertTrue(first_process["tx_data_df"].equals(data[0]["tx_data_df"]))  # DataFrame 应该保持不变

        result = self.processor.parse(data[1], dict(), list())

        # 检查结果
        self.assertIsNotNone(result)
        # 检查第二个进程（forward 进程）
        second_process = result
        self.assertIn("tx_data_df", second_process)
        second_df = second_process["tx_data_df"]
        self.assertEqual(second_df.iloc[0]["rid"], '20')  # rid 应该被正确映射

    def test_extract_rid_only(self):
        # 测试数据
        test_rid = [123, 456]

        # 执行测试
        result = self.processor.extract_rid(test_rid)
        
        # 验证结果
        self.assertEqual(result[0], "123,456")  # 转换后的rid字符串
        self.assertListEqual(result[1], [123, 456])
        self.assertListEqual(result[2], [None, None])
        self.assertListEqual(result[3], [])

    def test_missing_rid_column(self):
        # 准备测试数据
        test_df = pd.DataFrame({
            'other_col': [1, 2, 3]
        })
        rid_map = {"1": "11"}
        # 执行方法
        self.processor.process_each_df(test_df, rid_map)
        # 验证结果
        self.assertNotIn('res_list', test_df.columns)
        self.assertNotIn('rid_list', test_df.columns)
        self.assertNotIn('token_id_list', test_df.columns)

    def test_process_data_df_rid_correctly(self):
        # 准备测试数据
        test_df = pd.DataFrame({
            'rid': [[1], [2], [1, 2]],
            'other_col': ['a', 'b', 'c']
        })
        rid_map = {"1": "101", "2": "102"}

        # 执行方法
        self.processor.process_each_df(test_df, rid_map)

        # 验证结果
        self.assertIn('res_list', test_df.columns)
        self.assertIn('rid', test_df.columns)
        self.assertIn('rid_list', test_df.columns)
        self.assertIn('token_id_list', test_df.columns)
        self.assertIn('dp_list', test_df.columns)
        self.assertListEqual(
            test_df['res_list'].to_list(), [['101'], ['102'], ['101', '102']]
        )
        self.assertListEqual(test_df['rid'].to_list(), ['101', '102', '101,102'])
        self.assertListEqual(test_df['rid_list'].to_list(), [['101'], ['102'], ['101', '102']])

        def test_process_empty_dataframe(self):
            test_df = pd.DataFrame(columns=['rid'])
            rid_map = {}

            # 执行方法
            self.processor.process_each_df(test_df, rid_map)

            # 验证结果
            self.assertIn('res_list', test_df.columns)
            self.assertEqual(len(test_df), 0)  # 保持空数据框

    def test_process_data_df_token_id_correctly(self):
        # 准备测试数据
        test_df = pd.DataFrame({
            'rid': [
                [{'rid': 1, 'iter': '0'}, {'rid': 2, 'iter': '0'}],
                [{'rid': 1, 'iter': '1'}, {'rid': 2, 'iter': '1'}]
            ]
        })
        rid_map = {"1": "101", "2": "102"}

        # 执行方法
        self.processor.process_each_df(test_df, rid_map)

        # 验证结果
        self.assertListEqual(
            test_df['res_list'].to_list(),
            [[{'rid': '101', 'iter': '0'}, {'rid': '102', 'iter': '0'}],
            [{'rid': '101', 'iter': '1'}, {'rid': '102', 'iter': '1'}]]
        )
        self.assertListEqual(test_df['rid'].to_list(), ['101,102', '101,102'])
        self.assertListEqual(test_df['rid_list'].to_list(), [['101', '102'], ['101', '102']])
        self.assertListEqual(test_df['token_id_list'].to_list(), [['0', '0'], ['1', '1']])


    def test_process_data_df_dp_correctly(self):
        # 准备测试数据
        test_df = pd.DataFrame({
            'rid': [
                [{'rid': 1, 'dp': '0'}, {'rid': 2, 'dp': '0'}],
                [{'rid': 1, 'dp': '1'}, {'rid': 2, 'dp': '1'}]
            ]
        })
        rid_map = {"1": "101", "2": "102"}

        # 执行方法
        self.processor.process_each_df(test_df, rid_map)

        # 验证结果
        self.assertListEqual(
            test_df['res_list'].to_list(),
            [[{'rid': '101', 'dp': '0'}, {'rid': '102', 'dp': '0'}],
            [{'rid': '101', 'dp': '1'}, {'rid': '102', 'dp': '1'}]]
        )
        self.assertListEqual(test_df['rid'].to_list(), ['101,102', '101,102'])
        self.assertListEqual(test_df['rid_list'].to_list(), [['101', '102'], ['101', '102']])
        self.assertListEqual(test_df['dp_list'].to_list(), [['0', '0'], ['1', '1']])


if __name__ == "__main__":
    unittest.main()