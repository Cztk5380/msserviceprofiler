import os
import argparse
import unittest
import pandas as pd
from unittest.mock import patch
from ms_service_profiler.exporters.exporter_latency import (
    timestamp_converter,
    process_each_record,
    get_percentile_results,
    calculate_gen_token_speed_latency,
    calculate_first_token_latency,
    calculate_req_latency,
    gen_exporter_results,
    create_sqlite_db,
    save_to_sqlite_db,
    ExporterLatency
)


class TestTimestampConverter(unittest.TestCase):
    def test_timestamp_converter_suss(self):
        # 测试正常的时间戳
        timestamp = 1577836800000000
        result = timestamp_converter(timestamp)
        self.assertIn('2020-01-01', result)

    def test_process_each_record_httpReq(self):
        req_map = {}
        record = {'name': 'httpReq', 'rid': '1', 'start_time': '1577836800000000', \
            'rid_list': None, 'token_id_list': None}
        process_each_record(req_map, record)
        self.assertEqual(req_map['1']['start_time'], '1577836800000000')

    def test_process_each_record_httpRes(self):
        req_map = {'1': {'start_time': '1577836800000000'}}
        record = {'name': 'httpRes', 'rid': '1', 'end_time': '1577836800001000', \
            'rid_list': None, 'token_id_list': None}
        process_each_record(req_map, record)
        self.assertEqual(req_map['1']['end_time'], '1577836800001000')
        self.assertEqual(req_map['1']['gen_last_token_time'], '1577836800001000')

    def test_process_each_record_first_token_latency(self):
        req_map = {'1': {'start_time': '1577836800000000'}}
        record = {'name': 'modeExec', 'rid': '1', 'end_time': '1577836800001000', 'during_time': 10, \
            'rid_list': ['1'], 'token_id_list': [0]}
        process_each_record(req_map, record)
        self.assertEqual(req_map['1']['first_token_latency'], 10)

    def test_process_each_record_gen_token_num(self):
        req_map = {'1': {'start_time': '1577836800000000'}}
        record = {'name': 'modeExec', 'rid': '1', 'end_time': '1577836800001000', 'during_time': 10, \
            'rid_list': ['1'], 'token_id_list': [0]}
        process_each_record(req_map, record)
        self.assertEqual(req_map['1']['gen_token_num'], 1)
        self.assertEqual(req_map['1']['gen_last_token_time'], '1577836800001000')

    def test_get_empty_metric_percentile_results(self):
        self.assertEqual(get_percentile_results([]), {})

    def test_get_single_metric_percentile_results(self):
        metric = [10]
        self.assertEqual(get_percentile_results(metric), {'avg': 10.0, 'p99': 10.0, 'p90': 10.0, 'p50': 10.0})

    def test_get_multiple_metrics_percentile_results(self):
        metric = [10, 20, 30, 40, 50]
        self.assertEqual(get_percentile_results(metric), {'avg': 30.0, 'p99': 49.6, 'p90': 46.0, 'p50': 30.0})

    def test_calculate_first_token_latency_single_value(self):
        req_map = {'1': {'first_token_latency': 10}}
        self.assertEqual(calculate_first_token_latency(req_map), {'avg': 10.0, 'p99': 10.0, 'p90': 10.0, 'p50': 10.0})

    def test_calculate_first_token_latency_multiple_values(self):
        req_map = {'1': {'first_token_latency': 10}, '2': {'first_token_latency': 20}, \
            '3': {'first_token_latency': 30}, '4': {'first_token_latency': 40}, '5': {'first_token_latency': 50}}
        self.assertEqual(calculate_first_token_latency(req_map), {'avg': 30.0, 'p99': 49.6, 'p90': 46.0, 'p50': 30.0})

    def test_calculate_req_latency_single_req(self):
        req_map = {'1': {'start_time': 10, 'end_time': 20}}
        self.assertEqual(calculate_req_latency(req_map), {'avg': 10.0, 'p99': 10.0, 'p90': 10.0, 'p50': 10.0})

    def test_calculate_req_latency_multiple_reqs(self):
        req_map = {
            '1': {'start_time': 10, 'end_time': 20},
            '2': {'start_time': 15, 'end_time': 25},
            '3': {'start_time': 20, 'end_time': 30},
            '4': {'start_time': 25, 'end_time': 35},
            '5': {'start_time': 30, 'end_time': 40}
        }
        self.assertEqual(calculate_req_latency(req_map), {'avg': 10.0, 'p99': 10.0, 'p90': 10.0, 'p50': 10.0})

    def test_calculate_gen_token_speed_latency_multiple_req_map(self):
        req_map = {
            '1': {
                'start_time': 200,
                'gen_token_num': 200,
                'gen_last_token_time': 200000200
            },
            '2': {
                'start_time': 300,
                'gen_token_num': 300,
                'gen_last_token_time': 300000300
            }
        }
        result = calculate_gen_token_speed_latency(req_map)
        self.assertEqual(result, {'avg': 1.0, 'p99': 1.0, 'p90': 1.0, 'p50': 1.0})


    @patch('ms_service_profiler.exporters.exporter_latency.timestamp_converter')
    @patch('ms_service_profiler.exporters.exporter_latency.calculate_gen_token_speed_latency')
    @patch('ms_service_profiler.exporters.exporter_latency.calculate_req_latency')
    @patch('ms_service_profiler.exporters.exporter_latency.calculate_first_token_latency')
    @patch('ms_service_profiler.exporters.exporter_latency.process_each_record')
    def test_gen_exporter_results(self, mock_timestamp_converter, mock_calculate_gen_token_speed_latency, \
        mock_calculate_req_latency, mock_calculate_first_token_latency, mock_process_each_record):
        mock_data = {
            'batch_type': ['Prefill', 'Prefill', 'httpRes', 'httpRes', None],
            'name': ['Prefill', 'Prefill', 'httpRes', 'httpRes', 'httpRes'],
            'rid_list': [None, None, None, None, ['1', '2']],
            'end_time': ['1577836800001000', '1577836800002000', '1577836800003000', \
            '1577836800004000', '1577836800005000']
        }
        mock_df = pd.DataFrame(mock_data)

        # 调用测试的函数
        first_token_latency_view_data, req_latency_view_data, gen_token_speed_view_data = gen_exporter_results(mock_df)

        # 检查模拟函数是否被正确调用
        mock_process_each_record.assert_called()
        mock_calculate_first_token_latency.assert_called()
        mock_calculate_req_latency.assert_called()
        mock_calculate_gen_token_speed_latency.assert_called()
        mock_timestamp_converter.assert_called()

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('sqlite3.connect')
    def test_create_sqlite_db(self, mock_connect, mock_makedirs, mock_exists):
            # Test when the output directory does not exist
            mock_exists.return_value = False
            output = '/path/to/output'
            db_file = create_sqlite_db(output)
            mock_makedirs.assert_called_once_with(output)
            mock_connect.assert_called_once_with(os.path.join(output, '.profiler.db'))
            self.assertEqual(db_file, os.path.join(output, '.profiler.db'))

    @patch('sqlite3.connect')
    def test_save_to_sqlite_db(self, mock_connect):
        db_file_path = 'test.db'
        table_name = 'test_table'
        view_data = {
            '2020-01-01 00:00:00': {
                'avg': 1.0,
                'p99': 2.0,
                'p90': 3.0,
                'p50': 4.0
            },
            '2020-01-01 01:00:00': {
                'avg': 5.0,
                'p99': 6.0,
                'p90': 7.0,
                'p50': 8.0
            }
        }
        save_to_sqlite_db(db_file_path, table_name, view_data)
        mock_connect.assert_called_once_with(db_file_path)


if __name__ == '__main__':
    unittest.main()