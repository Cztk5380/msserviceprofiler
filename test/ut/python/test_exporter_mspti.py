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
import unittest
from unittest.mock import patch, MagicMock

import pandas as pd

from ms_service_profiler.exporters.exporter_mspti import ExporterMspti, export_event_from_df
from ms_service_profiler.utils.trace_to_db import TRACE_TABLE_DEFINITIONS
from ms_service_profiler.utils.log import logger


class TestExporterMspti(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 设置测试所需的公共资源
        cls.api_df = pd.DataFrame({
            "name": ["api1", "api2"],
            "start": [1000, 2000],
            "end": [1500, 2500],
            "db_id": [1, 2]
        })
        cls.kernel_df = pd.DataFrame({
            "name": ["kernel1", "kernel2"],
            "start": [1200, 2200],
            "end": [1300, 2300],
            "db_id": [1, 2]
        })
        cls.data = {"api_df": cls.api_df, "kernel_df": cls.kernel_df}

    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_json')
    @patch('ms_service_profiler.exporters.exporter_mspti.create_sqlite_tables')
    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_db')
    def test_export_to_json(self, mock_save_db, mock_create_tables, mock_save_json):
        # 设置测试参数
        ExporterMspti.args = MagicMock()
        ExporterMspti.args.format = ['json']
        ExporterMspti.args.output_path = 'test_output.json'

        # 调用export方法
        ExporterMspti.export(self.data)

        # 验证是否调用了save_trace_data_into_json
        mock_save_json.assert_called_once()
        mock_save_db.assert_not_called()
        mock_create_tables.assert_not_called()

    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_json')
    @patch('ms_service_profiler.exporters.exporter_mspti.create_sqlite_tables')
    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_db')
    def test_export_to_db(self, mock_save_db, mock_create_tables, mock_save_json):
        # 设置测试参数
        ExporterMspti.args = MagicMock()
        ExporterMspti.args.format = ['db']
        ExporterMspti.args.output_path = 'test_output.db'

        # 调用export方法
        ExporterMspti.export(self.data)

        # 验证是否调用了相关函数
        mock_save_json.assert_not_called()
        mock_create_tables.assert_called_once_with(TRACE_TABLE_DEFINITIONS)
        mock_save_db.assert_called_once()

    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_json')
    @patch('ms_service_profiler.exporters.exporter_mspti.create_sqlite_tables')
    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_db')
    def test_export_to_both(self, mock_save_db, mock_create_tables, mock_save_json):
        # 设置测试参数
        ExporterMspti.args = MagicMock()
        ExporterMspti.args.format = ['json', 'db']
        ExporterMspti.args.output_path = 'test_output'

        # 调用export方法
        ExporterMspti.export(self.data)

        # 验证是否调用了所有相关函数
        mock_save_json.assert_called_once()
        mock_create_tables.assert_called_once_with(TRACE_TABLE_DEFINITIONS)
        mock_save_db.assert_called_once()

    def test_export_event_from_df(self):
        # 测试export_event_from_df函数
        events = export_event_from_df(self.api_df, "Api", 0)
        self.assertEqual(len(events), len(self.api_df) + len(set(self.api_df["db_id"])))

        # 验证生成的事件格式
        for event in events:
            self.assertIn("name", event)
            self.assertIn("ph", event)
            self.assertIn("pid", event)
            self.assertIn("tid", event)
            self.assertIn("args", event)

        # 验证process_name事件
        process_names = [event for event in events if event["ph"] == "M"]
        self.assertEqual(len(process_names), len(set(self.api_df["db_id"])))

        for process_name_event in process_names:
            self.assertEqual(process_name_event["name"], "thread_name")
            self.assertIn("args", process_name_event)
            self.assertIn("name", process_name_event["args"])


    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_json')
    @patch('ms_service_profiler.exporters.exporter_mspti.create_sqlite_tables')
    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_db')
    def test_export_no_format(self, mock_save_db, mock_create_tables, mock_save_json):
        # 设置测试参数，format既不包含'db'也不包含'json'
        ExporterMspti.args = MagicMock()
        ExporterMspti.args.format = ['other']
        ExporterMspti.args.output_path = 'test_output'

        # 调用export方法
        ExporterMspti.export(self.data)

        # 验证没有调用任何保存函数
        mock_save_json.assert_not_called()
        mock_create_tables.assert_not_called()
        mock_save_db.assert_not_called()

    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_json')
    @patch('ms_service_profiler.exporters.exporter_mspti.create_sqlite_tables')
    @patch('ms_service_profiler.exporters.exporter_mspti.save_trace_data_into_db')
    def test_export_empty_data(self, mock_save_db, mock_create_tables, mock_save_json):
        # 设置测试参数
        ExporterMspti.args = MagicMock()
        ExporterMspti.args.format = ['json', 'db']
        ExporterMspti.args.output_path = 'test_output'

        # 调用export方法，传入空数据
        ExporterMspti.export({})

        # 验证没有调用任何保存函数
        mock_save_json.assert_not_called()
        mock_create_tables.assert_not_called()
        mock_save_db.assert_not_called()

    def test_depends(self):
        # 测试depends方法
        dependencies = ExporterMspti.depends()
        self.assertEqual(dependencies, ["pipeline:mspti"])


if __name__ == '__main__':
    unittest.main()