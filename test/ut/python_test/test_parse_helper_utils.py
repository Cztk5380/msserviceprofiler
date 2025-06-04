# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import datetime
import logging

from concurrent.futures import ProcessPoolExecutor
import pandas as pd

from ms_service_profiler.parse_helper.utils import _convert_db_to_df, convert_db_to_df, convert_timestamp
from ms_service_profiler.parse_helper.constant import MAJOR_TABLE_COLS, \
    MAJOR_TABLE_NAME, MINOR_TABLE_COLS, MINOR_TABLE_NAME


# 配置日志记录器
logger = logging.getLogger(__name__)


class TestDBConversion(unittest.TestCase):

    @patch('ms_service_profiler.parse_helper.utils.pd.read_sql_query')
    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_major_query_success(self, mock_sqlite3_connect, mock_read_sql_query):
        # 模拟数据库连接和查询结果
        mock_read_sql_query.return_value = pd.DataFrame({'markId': [1, 2], 'col1': ['a', 'b']})
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.return_value = [('col2', [3, 4])]

        file_path = 'test.db'
        result = _convert_db_to_df(file_path)

        self.assertIsNotNone(result)
        self.assertIn('markId', result.columns)
        self.assertIn('col1', result.columns)
        self.assertIn('col2', result.columns)
        self.assertEqual(len(result), 2)
        mock_read_sql_query.assert_called_once_with(
            f"SELECT {','.join(MAJOR_TABLE_COLS)} FROM {MAJOR_TABLE_NAME} order by markId", mock_conn)
        mock_cursor.execute.assert_called_once_with(f"SELECT {','.join(MINOR_TABLE_COLS)} FROM {MINOR_TABLE_NAME}")


    @patch('ms_service_profiler.parse_helper.utils.pd.read_sql_query')
    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_major_query_failure(self, mock_sqlite3_connect, mock_read_sql_query):
        # 模拟查询失败
        mock_read_sql_query.side_effect = Exception('Mocked exception')
        mock_logger = MagicMock()
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result = _convert_db_to_df(file_path)

            self.assertTrue(result.empty)
            mock_logger.warning.assert_called_once()


    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_minor_query_failure(self, mock_sqlite3_connect):
        # 模拟次要表查询失败
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception('Mocked exception')
        mock_logger = MagicMock()
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result = _convert_db_to_df(file_path)

            self.assertTrue(result.empty)
            mock_logger.warning.assert_called_once()


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
        # 测试主表查询抛出异常的情况
        mock_read_sql_query.side_effect = Exception('Mocked major query exception')
        mock_logger = MagicMock()
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result = _convert_db_to_df(file_path)

            self.assertTrue(result.empty)  # 确保返回的 DataFrame 是空的
            mock_logger.warning.assert_called_once()  # 确保 logger.warning 被调用了一次


    @patch('ms_service_profiler.parse_helper.utils.sqlite3.connect')
    def test_convert_db_to_df_minor_query_exception(self, mock_sqlite3_connect):
        # 测试次要表查询抛出异常的情况
        mock_conn = mock_sqlite3_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception('Mocked minor query exception')
        mock_logger = MagicMock()
        with patch('ms_service_profiler.parse_helper.utils.logger', mock_logger):
            file_path = 'test.db'
            result = _convert_db_to_df(file_path)

            self.assertTrue(result.empty)  # 确保返回的 DataFrame 是空的
            mock_logger.warning.assert_called_once()  # 确保 logger.warning 被调用了一次


if __name__ == '__main__':
    unittest.main()