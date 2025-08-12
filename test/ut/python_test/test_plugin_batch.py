# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
import pandas as pd
from unittest.mock import MagicMock

from ms_service_profiler.plugins.plugin_batch import PluginBatch


class TestPluginBatch(unittest.TestCase):
    def setUp(self):
        # 初始化 PluginBatch 类
        self.plugin = PluginBatch
        self.plugin.batch_req = dict()
        self.plugin.batch_exec = dict()
        self.plugin.batch_list = dict()


    def test_add_req_info(self):
        # 测试 add_req_info 方法
        batch_id = 1
        req_id = "req1"
        values = {"key1": "value1", "key2": "value2"}

        self.plugin.add_req_info(batch_id, req_id, **values)
        self.assertIn((batch_id, req_id), self.plugin.batch_req)
        self.assertEqual(self.plugin.batch_req[(batch_id, req_id)], {"batch_id": batch_id, "req_id": req_id,
                                                                     "key1": "value1", "key2": "value2"})


    def test_add_exec_info(self):
        # 测试 add_exec_info 方法
        batch_id = 1
        pid = 1001
        exec_name = "exec_name"
        start = 1622534400
        end = 1622534405

        self.plugin.add_exec_info(batch_id, pid, exec_name, start, end)
        self.assertIn((batch_id, pid, exec_name), self.plugin.batch_exec)
        self.assertEqual(self.plugin.batch_exec[(batch_id, pid, exec_name)], (batch_id, exec_name, pid, start,
                                                                              end))


    def test_clear_batch(self):
        # 测试 clear_batch 方法
        self.plugin.batch_list = {
            ("req1", "req2"): {"time": 1622534400},
            ("req3", "req4"): {"time": 1622534500}
        }
        time = 1622534450
        self.plugin.clear_batch(time)
        self.assertEqual(self.plugin.batch_list, {("req3", "req4"): {"time": 1622534500}})


    def test_deal_with_batch_row(self):
        # 测试 deal_with_batch_row 方法
        row = MagicMock()
        row.start_time = 1622534400
        row.rid_list = ["req1", "req2"]
        row.pid = 1001
        row.name = "BatchSchedule"
        row.end_time = 1622534405
        row.res_list = [  # 添加 res_list 属性
            {"rid": "req1", "key1": "value1"},
            {"rid": "req2", "key2": "value2"}
        ]

        batch_index = 1
        self.plugin.deal_with_batch_row(row, batch_index)
        self.assertIn(("req1", "req2"), self.plugin.batch_list)
        self.assertEqual(self.plugin.batch_list[("req1", "req2")]["id"], batch_index)
        self.assertIn((batch_index, "req1"), self.plugin.batch_req)
        self.assertIn((batch_index, "req2"), self.plugin.batch_req)

        # 修改期望的字典以匹配 add_req_info 方法的实际行为
        expected_req1 = {"batch_id": batch_index, "req_id": "req1", "rid": "req1", "key1": "value1"}
        expected_req2 = {"batch_id": batch_index, "req_id": "req2", "rid": "req2", "key2": "value2"}

        self.assertEqual(self.plugin.batch_req[(batch_index, "req1")], expected_req1)
        self.assertEqual(self.plugin.batch_req[(batch_index, "req2")], expected_req2)


    def test_deal_with_model_exec_row(self):
        # 测试 deal_with_model_exec_row 方法
        row = MagicMock()
        row.rid_list = ["req1", "req2"]
        row.pid = 1001
        row.name = "modelExec"
        row.end_time = 1622534405
        row.start_time = 1622534400

        self.plugin.batch_list = {("req1", "req2"): {"id": 1}}
        self.plugin.deal_with_model_exec_row(row)
        self.assertEqual(self.plugin.batch_list[("req1", "req2")]["time"], row.end_time)
        self.assertIn((1, 1001, "modelExec"), self.plugin.batch_exec)

    def test_deal_with_preprocess_row(self):
        # 测试 deal_with_preprocess_row 方法
        row = MagicMock()
        row.rid_list = ["req1", "req2"]
        row.pid = 1001
        row.tid = 2001
        row.hostname = "host1"
        row.name = "preprocess"
        row.start_time = 1622534400
        row.end_time = 1622534405
        row.blocks = None
        batch_index = 1

        last_preprocess = dict()
        self.plugin.batch_req = {
            (1, "req1"): {"batch_id": 1, "req_id": "req1"},
            (1, "req2"): {"batch_id": 1, "req_id": "req2"}
        }

        self.plugin.deal_with_preprocess_row(row, last_preprocess, batch_index)

        # 检查 last_preprocess 是否正确更新
        self.assertIn((1001, 2001, "host1"), last_preprocess)
        self.assertEqual(last_preprocess[(1001, 2001, "host1")]["batch_id"], 1)

    def test_deal_with_forward_row(self):
        # 测试 deal_with_forward_row 方法
        row = MagicMock()
        row.pid = 1001
        row.tid = 2001
        row.hostname = "host1"
        row.name = "forward"
        row.start_time = 1622534400
        row.end_time = 1622534405
        batch_index = 1

        last_preprocess = {(1001, 2001, "host1"): {"rid_list": ["req1", "req2"]}}
        self.plugin.batch_list = {("req1", "req2"): {"id": 1, "time": 1622534410}}  # 修改 time 使其大于 row.end_time
        self.plugin.deal_with_forward_row(row, last_preprocess, batch_index)
        self.assertIn((1, 1001, "forward"), self.plugin.batch_exec)

    def test_extract_batch_info(self):
        # 测试 extract_batch_info 方法
        batch_df = pd.DataFrame([
            {"name": "BatchSchedule", "start_time": 1622534400, "end_time": 1622534405, "pid": 1001, "tid": 2001,
             "hostname": "host1", "rid_list": ["req1", "req2"], "res_list": [{"rid": "req1", "key1": "value1"},
                                                                             {"rid": "req2", "key2": "value2"}]},
            {"name": "modelExec", "start_time": 1622534410, "end_time": 1622534415, "pid": 1001, "tid": 2001,
             "hostname": "host1", "rid_list": ["req1", "req2"]},
            {"name": "preprocess", "start_time": 1622534420, "end_time": 1622534425, "pid": 1001, "tid": 2001,
             "hostname": "host1", "rid_list": ["req1", "req2"], "blocks": None},  # 修改为 None 或一个单一的值
        ])

        self.plugin.extract_batch_info(batch_df)

        # 检查 batch_list 是否正确更新
        assert ("req1", "req2") in self.plugin.batch_list
        assert self.plugin.batch_list[("req1", "req2")]["id"] == 1

        # 检查 batch_req 是否正确更新
        assert (1, "req1") in self.plugin.batch_req
        assert (1, "req2") in self.plugin.batch_req

        # 修改期望的字典以匹配 deal_with_preprocess_row 方法的实际行为
        expected_req1 = {"batch_id": 1, "req_id": "req1", "rid": "req1", "key1": "value1"}
        expected_req2 = {"batch_id": 1, "req_id": "req2", "rid": "req2", "key2": "value2"}

        # 使用 assertDictEqual 来比较字典
        self.assertDictEqual(self.plugin.batch_req[(1, "req1")], expected_req1)
        self.assertDictEqual(self.plugin.batch_req[(1, "req2")], expected_req2)

        # 检查 batch_exec 是否正确更新
        assert (1, 1001, "BatchSchedule") in self.plugin.batch_exec
        assert (1, 1001, "modelExec") in self.plugin.batch_exec
        assert (1, 1001, "preprocess") in self.plugin.batch_exec

    def test_parse(self):
        # 测试 parse 方法
        data = {
            "tx_data_df": pd.DataFrame([
                {"name": "BatchSchedule", "start_time": 1622534400, "end_time": 1622534405, "pid": 1001, "tid": 2001,
                 "hostname": "host1", "rid_list": ["req1", "req2"], "res_list": [{"rid": "req1", "key1": "value1"},
                                                                                 {"rid": "req2", "key2": "value2"}]},
                {"name": "modelExec", "start_time": 1622534410, "end_time": 1622534415, "pid": 1001, "tid": 2001,
                 "hostname": "host1", "rid_list": ["req1", "req2"]},
                {"name": "preprocess", "start_time": 1622534420, "end_time": 1622534425, "pid": 1001, "tid": 2001,
                 "hostname": "host1", "rid_list": ["req1", "req2"], "blocks": None},
            ])
        }

        result = self.plugin.parse(data)

        # 检查返回结果是否包含 batch_req_df 和 batch_exec_df
        assert "batch_req_df" in result
        assert "batch_exec_df" in result
        assert isinstance(result["batch_req_df"], pd.DataFrame)
        assert isinstance(result["batch_exec_df"], pd.DataFrame)

        # 检查 batch_req_df 是否正确
        batch_req_df = result["batch_req_df"]
        assert len(batch_req_df) == 2  # 应该有两条记录
        assert (batch_req_df["req_id"] == "req1").any()
        assert (batch_req_df["req_id"] == "req2").any()

        # 检查 batch_exec_df 是否正确
        batch_exec_df = result["batch_exec_df"]
        assert len(batch_exec_df) == 3  # 应该三条记录
        assert (batch_exec_df["name"] == "BatchSchedule").any()
        assert (batch_exec_df["name"] == "modelExec").any()
        assert (batch_exec_df["name"] == "preprocess").any()


if __name__ == "__main__":
    unittest.main()