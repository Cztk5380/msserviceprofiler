# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import argparse
import unittest
from unittest.mock import patch
import pandas as pd
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

    def test_process_each_record_request(self):
        req_map = {}
        record = {'name': 'httpReq', 'rid': '1', 'start_time': '1577836800000000', \
            'rid_list': None, 'token_id_list': None, 'end_time': '1577836800001000'}
        process_each_record(req_map, record)
        if '1' in req_map and 'start_time' in req_map['1']:
            self.assertEqual(req_map['1']['start_time'], '1577836800000000')
        else:
            raise KeyError("Key '1' or 'start_time' does not exist in req_map.")

    def test_process_each_record_response(self):
        req_map = {'1': {'start_time': '1577836800000000'}}
        record = {'name': 'httpRes', 'rid': '1', 'end_time': '1577836800001000', \
            'rid_list': None, 'token_id_list': None}
        process_each_record(req_map, record)
        if 'end_time' in req_map['1'] and 'req_exec_time' in req_map['1']:
            self.assertEqual(req_map['1']['end_time'], '1577836800001000')
            self.assertEqual(req_map['1']['req_exec_time'], '1577836800001000')
        else:
            raise KeyError("Key 'end_time' or 'req_exec_time' does not exist in req_map.")

    def test_process_each_record_first_token_latency(self):
        req_map = {'1': {'start_time': '1577836800000000'}}
        record = {'name': 'modeExec', 'rid': '1', 'end_time': '1577836800001000', 'during_time': 10, \
            'rid_list': ['1'], 'token_id_list': [0], 'batch_type': 'Prefill'}
        process_each_record(req_map, record)
        if 'first_token_latency' in req_map['1']:
            self.assertEqual(req_map['1']['first_token_latency'], 10)
        else:
            raise KeyError("Key 'first_token_latency' does not exist in req_map.")

    def test_process_each_record_prefill_token_num(self):
        req_map = {'1': {'start_time': '1577836800000000'}}
        record = {'name': 'modeExec', 'rid': '1', 'end_time': '1577836800001000', 'during_time': 10, \
            'rid_list': ['1'], 'token_id_list': [0], 'batch_type': 'Prefill'}
        process_each_record(req_map, record)
        if 'prefill_token_num' in req_map['1'] and 'req_exec_time' in req_map['1']:
            self.assertEqual(req_map['1']['prefill_token_num'], 1)
            self.assertEqual(req_map['1']['req_exec_time'], '1577836800001000')
        else:
            raise KeyError("Key 'prefill_token_num' or 'req_exec_time' does not exist in req_map.")

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

    def test_calculate_prefill_gen_token_speed_latency(self):
        # 测试prefill情况下的token生成速度和延迟
        req_map = {
            '1': {'start_time': 100000000, 'prefill_token_num': 100, 'req_exec_time': 200000000},
            '2': {'start_time': 100000000, 'prefill_token_num': 200, 'req_exec_time': 300000000},
        }
        result = calculate_gen_token_speed_latency(req_map, True)
        self.assertEqual(result, {'avg': 1, 'p99': 1, 'p90': 1, 'p50': 1})

    def test_calculate_decode_gen_token_speed_latency(self):
        # 测试decode情况下的token生成速度和延迟
        req_map = {
            '1': {'start_time': 100000000, 'decode_token_num': 100, 'req_exec_time': 200000000},
            '2': {'start_time': 100000000, 'decode_token_num': 200, 'req_exec_time': 300000000},
        }
        result = calculate_gen_token_speed_latency(req_map, False)
        self.assertEqual(result, {'avg': 1, 'p99': 1, 'p90': 1, 'p50': 1})


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
            'rid_list': [['1', '2'], None, None, None, None],
            'token_id_list': [['0', '1'], None, None, None, None],
            'end_time': ['1577836800001000', '1577836800002000', '1577836800003000', \
            '1577836800004000', '1577836800005000']
        }
        all_data_df = pd.DataFrame(mock_data)

        first_token_latency_views, req_latency_views, prefill_gen_speed_views, decode_gen_speed_views = \
            gen_exporter_results(all_data_df)

        mock_process_each_record.assert_called()
        mock_calculate_first_token_latency.assert_called()
        mock_calculate_req_latency.assert_called()
        mock_calculate_gen_token_speed_latency.assert_called()
        mock_timestamp_converter.assert_called()

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