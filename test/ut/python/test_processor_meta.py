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

import unittest
import pandas as pd
from ms_service_profiler.processor.processor_meta import ProcessorMeta

class TestProcessorMeta(unittest.TestCase):
    def setUp(self):
        self.processor = ProcessorMeta()

    def test_convert_to_format_str(self):
        self.assertEqual(self.processor.convert_to_format_str("123"), "123")
        self.assertEqual(self.processor.convert_to_format_str("abc"), "abc")
        self.assertEqual(self.processor.convert_to_format_str(123), "123")
        self.assertEqual(self.processor.convert_to_format_str("123.45"), "123.45")

    def test_parse_process_info(self):
        # 测试空数据帧
        data_df = pd.DataFrame()
        result = self.processor.parse_process_info(data_df)
        self.assertEqual(result, {})

        # 测试缺少必要列的数据帧
        data_df = pd.DataFrame({"hostname": ["host1"], "pid": [123]})
        result = self.processor.parse_process_info(data_df)
        self.assertEqual(result, {})

        # 测试正常数据帧
        data_df = pd.DataFrame({
            "hostname": ["host1", "host2"],
            "pid": [123, 456],
            "name": ["task1", "forward"],
            "from": [None, "src1"],
            "to": [None, "dst1"],
            "ppid": ['789', None],
            "deviceid": [None, "0"]
        })
        result = self.processor.parse_process_info(data_df)
        expected_result = {
            "hostname": "host2",
            "pid": "456",
            "ppid": "789",
            "device_id": "0",
            "is_forward": True,
            "rid_map": {"dst1": "src1"}
        }
        self.assertEqual(result, expected_result)

    def test_parse(self):
        data = {
            "tx_data_df": pd.DataFrame({
                "hostname": ["host1", "host2"],
                "pid": [123, 456],
                "name": ["task1", "forward"],
                "from": [None, "src1"],
                "to": [None, "dst1"],
                "ppid": ['789', None],
                "deviceid": [None, "0"]
            }),
            "meta": {}
        }
        result = self.processor.parse(data)
        expected_result = {
            "hostname": "host2",
            "pid": "456",
            "ppid": "789",
            "device_id": "0",
            "is_forward": True,
            "rid_map": {"dst1": "src1"}
        }
        self.assertEqual(result, expected_result)

if __name__ == '__main__':
    unittest.main()