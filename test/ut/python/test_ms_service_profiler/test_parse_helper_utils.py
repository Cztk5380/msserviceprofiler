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
from unittest.mock import patch, MagicMock
import sqlite3
import datetime
import logging

from concurrent.futures import ProcessPoolExecutor
import pandas as pd

from ms_service_profiler.parse_helper.utils import convert_db_to_df, convert_timestamp, _convert_slice_to_mstx_format
from ms_service_profiler.parse_helper.constant import MAJOR_TABLE_COLS, \
    MAJOR_TABLE_NAME, MINOR_TABLE_COLS, MINOR_TABLE_NAME, SLICE_TABLE_COLS, SLICE_TABLE_NAME


# 配置日志记录器
logger = logging.getLogger(__name__)


class TestDBConversion(unittest.TestCase):

    @patch('ms_service_profiler.parse_helper.utils.pd.read_sql_query')
    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_major_query_success(self, mock_sqlite3_connect, mock_read_sql_query):
        mock_read_sql_query.return_value = pd.DataFrame({'markId': [1, 2], 'col1': ['a', 'b']})
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.side_effect = [
            [],  # SELECT name FROM sqlite_master returns empty (no slice table)
            [],  # PRAGMA table_info returns empty (no slice column)
            [('col2', [3, 4])]  # minor query data
        ]

        file_path = 'test.db'
        result, _, _ = convert_db_to_df(file_path)

        self.assertIsNotNone(result)
        self.assertIn('markId', result.columns)
        self.assertIn('col1', result.columns)
        self.assertIn('col2', result.columns)
        self.assertEqual(len(result), 2)
        mock_read_sql_query.assert_called_once_with(
            f"SELECT {','.join(MAJOR_TABLE_COLS)} FROM {MAJOR_TABLE_NAME} order by markId", mock_conn)
        self.assertEqual(mock_cursor.execute.call_count, 3)


    @patch('ms_service_profiler.parse_helper.utils.pd.read_sql_query')
    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_major_query_failure(self, mock_sqlite3_connect, mock_read_sql_query):
        mock_read_sql_query.side_effect = Exception('Mocked exception')
        mock_logger = MagicMock()
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.side_effect = [
            [],  # SELECT name FROM sqlite_master returns empty (no slice table)
            [],  # PRAGMA table_info returns empty (no slice column)
            [('col2', [3, 4])]  # minor query data
        ]
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result, _, _ = convert_db_to_df(file_path)

            self.assertTrue(result.empty)
            mock_logger.warning.assert_called()


    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_minor_query_failure(self, mock_sqlite3_connect):
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.side_effect = [
            [],  # SELECT name FROM sqlite_master returns empty (no slice table)
            [],  # PRAGMA table_info returns empty (no slice column)
            Exception('Mocked exception')  # minor query fails
        ]
        mock_logger = MagicMock()
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result, _, _ = convert_db_to_df(file_path)

            self.assertTrue(result.empty)
            mock_logger.warning.assert_called()


    def test_convert_timestamp_valid(self):
        # 测试有效的时间戳转换
        timestamp = 1680307200000000  # 示例时间戳
        result = convert_timestamp(timestamp)
        self.assertIsInstance(result, str)
        self.assertRegex(result, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}:\d{6}$')


    def test_convert_timestamp_invalid(self):
        # 测试无效的时间戳转换
        timestamp = 'invalid_timestamp'
        mock_logger = MagicMock()
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            result = convert_timestamp(timestamp)
            self.assertEqual(result, timestamp)
            mock_logger.warning.assert_called_once()


    @patch('ms_service_profiler.parse_helper.utils.pd.read_sql_query')
    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_major_query_exception(self, mock_sqlite3_connect, mock_read_sql_query):
        mock_read_sql_query.side_effect = Exception('Mocked major query exception')
        mock_logger = MagicMock()
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.side_effect = [
            [],  # SELECT name FROM sqlite_master returns empty (no slice table)
            [],  # PRAGMA table_info returns empty (no slice column)
            [('col2', [3, 4])]  # minor query data
        ]
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result, _, _ = convert_db_to_df(file_path)

            self.assertTrue(result.empty)
            mock_logger.warning.assert_called()


    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_minor_query_exception(self, mock_sqlite3_connect):
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.side_effect = [
            [],  # SELECT name FROM sqlite_master returns empty (no slice table)
            [],  # PRAGMA table_info returns empty (no slice column)
            Exception('Mocked minor query exception')  # minor query fails
        ]
        mock_logger = MagicMock()
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result, _, _ = convert_db_to_df(file_path)

            self.assertTrue(result.empty)
            mock_logger.warning.assert_called()

    @patch('ms_service_profiler.parse_helper.utils.pd.read_sql_query')
    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_slice_logic(self, mock_sqlite3_connect, mock_read_sql_query):
        mock_slice_df = pd.DataFrame({
            'id': [1, 2],
            'timestamp': [1623456789000000, 1623456889000000],
            'duration': [100, 200],
            'name': ['task1', 'task2'],
            'depth': [0, 0],
            'track_id': [1, 2],
            'cat': ['domain1', 'domain2'],
            'args': ['{"key": "value1"}', '{"key": "value2"}'],
            'cname': ['color1', 'color2'],
            'end_time': [1623456799000000, 1623456899000000],
            'flag_id': [0, 0],
            'pid': [100, 200],
            'tid': [1000, 2000]
        })
        mock_read_sql_query.return_value = mock_slice_df
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.return_value = None
        mock_cursor.fetchall.side_effect = [
            [('slice_table',), ('other_table',)],  # SELECT name FROM sqlite_master returns slice table
            [(0, 'slice', 'text', 0, None, 0)],  # PRAGMA table_info returns slice column
            [('hostname', 'test_host')]  # minor query data
        ]

        file_path = 'test.db'
        result, meta, use_slice_logic = convert_db_to_df(file_path)

        self.assertTrue(use_slice_logic)
        self.assertIn('markId', result.columns)
        self.assertIn('domain', result.columns)
        self.assertIn('message', result.columns)
        self.assertIn('hostname', result.columns)
        self.assertEqual(result['hostname'].iloc[0], 'test_host')

    def test_convert_slice_to_mstx_format(self):
        # 测试 _convert_slice_to_mstx_format 函数
        slice_df = pd.DataFrame({
            'id': [1, 2],
            'timestamp': [1623456789000000, 1623456889000000],
            'cat': ['domain1', 'domain2'],
            'args': ['{"key": "value1"}', '{"key": "value2"}'],
            'pid': [100, 200],
            'tid': [1000, 2000],
            'name': ['task1', 'task2'],
            'duration': [100, 200],
            'depth': [0, 0],
            'track_id': [1, 2],
            'cname': ['color1', 'color2'],
            'end_time': [1623456799000000, 1623456899000000],
            'flag_id': [0, 0]
        })
        meta = {'hostname': 'test_host', 'service_type': 'test'}

        result = _convert_slice_to_mstx_format(slice_df, meta)

        self.assertIn('markId', result.columns)
        self.assertIn('domain', result.columns)
        self.assertIn('message', result.columns)
        self.assertIn('hostname', result.columns)
        self.assertEqual(result['markId'].tolist(), [1, 2])
        self.assertEqual(result['domain'].tolist(), ['domain1', 'domain2'])
        self.assertEqual(result['hostname'].iloc[0], 'test_host')

if __name__ == '__main__':
    unittest.main()