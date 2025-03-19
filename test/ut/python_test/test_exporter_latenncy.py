# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import argparse
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from ms_service_profiler.exporters.exporter_latency import (
    process_each_record,
    get_percentile_results,
    calculate_gen_token_speed_latency,
    is_contained_vaild_iter_info,
    calculate_first_token_latency,
    calculate_req_latency,
    gen_exporter_results,
    print_warning_log,
    ExporterLatency
)


class TestTimestampConverter(unittest.TestCase):
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
        self.assertEqual(get_percentile_results([]), (np.nan, np.nan, np.nan, np.nan))

    def test_get_single_metric_percentile_results(self):
        metric = [10]
        avg, p50, p90, p99 = get_percentile_results(metric)
        self.assertEqual(avg, 10.0)
        self.assertEqual(p50, 10.0)
        self.assertEqual(p90, 10.0)
        self.assertEqual(p99, 10.0)

    def test_get_multiple_metrics_percentile_results(self):
        metric = [10, 20, 30, 40, 50]
        avg, p50, p90, p99 = get_percentile_results(metric)
        self.assertEqual(avg, 30.0)
        self.assertEqual(p50, 30.0)
        self.assertEqual(p90, 46.0)
        self.assertEqual(p99, 49.6)

    def test_calculate_first_token_latency_single_value(self):
        req_map = {'1': {'first_token_latency': 10}}
        avg, p50, p90, p99 = calculate_first_token_latency(req_map)
        self.assertEqual(avg, 10.0)
        self.assertEqual(p50, 10.0)
        self.assertEqual(p90, 10.0)
        self.assertEqual(p99, 10.0)

    def test_calculate_first_token_latency_multiple_values(self):
        req_map = {'1': {'first_token_latency': 10}, '2': {'first_token_latency': 20}, \
            '3': {'first_token_latency': 30}, '4': {'first_token_latency': 40}, '5': {'first_token_latency': 50}}
        avg, p50, p90, p99 = calculate_first_token_latency(req_map)
        self.assertEqual(avg, 30.0)
        self.assertEqual(p50, 30.0)
        self.assertEqual(p90, 46.0)
        self.assertEqual(p99, 49.6)

    def test_calculate_req_latency_single_req(self):
        req_map = {'1': {'start_time': 10, 'end_time': 20}}
        avg, p50, p90, p99 = calculate_req_latency(req_map)
        self.assertEqual(avg, 10.0)
        self.assertEqual(p50, 10.0)
        self.assertEqual(p90, 10.0)
        self.assertEqual(p99, 10.0)

    def test_calculate_req_latency_multiple_reqs(self):
        req_map = {
            '1': {'start_time': 10, 'end_time': 20},
            '2': {'start_time': 15, 'end_time': 25},
            '3': {'start_time': 20, 'end_time': 30},
            '4': {'start_time': 25, 'end_time': 35},
            '5': {'start_time': 30, 'end_time': 40}
        }
        avg, p50, p90, p99 = calculate_req_latency(req_map)
        self.assertEqual(avg, 10.0)
        self.assertEqual(p50, 10.0)
        self.assertEqual(p90, 10.0)
        self.assertEqual(p99, 10.0)

    def test_calculate_prefill_gen_token_speed_latency(self):
        # 测试prefill情况下的token生成速度和延迟
        req_map = {
            '1': {'start_time': 100000000, 'prefill_token_num': 100, 'req_exec_time': 200000000},
            '2': {'start_time': 100000000, 'prefill_token_num': 200, 'req_exec_time': 300000000},
        }
        avg, p50, p90, p99 = calculate_gen_token_speed_latency(req_map, True)
        self.assertEqual(avg, 1)
        self.assertEqual(p50, 1)
        self.assertEqual(p90, 1)
        self.assertEqual(p99, 1)

    def test_calculate_decode_gen_token_speed_latency(self):
        # 测试decode情况下的token生成速度和延迟
        req_map = {
            '1': {'start_time': 100000000, 'decode_token_num': 100, 'req_exec_time': 200000000},
            '2': {'start_time': 100000000, 'decode_token_num': 200, 'req_exec_time': 300000000},
        }
        avg, p50, p90, p99 = calculate_gen_token_speed_latency(req_map, False)
        self.assertEqual(avg, 1)
        self.assertEqual(p50, 1)
        self.assertEqual(p90, 1)
        self.assertEqual(p99, 1)


    @patch('ms_service_profiler.exporters.exporter_latency.calculate_gen_token_speed_latency')
    @patch('ms_service_profiler.exporters.exporter_latency.calculate_req_latency')
    @patch('ms_service_profiler.exporters.exporter_latency.calculate_first_token_latency')
    @patch('ms_service_profiler.exporters.exporter_latency.process_each_record')
    def test_gen_exporter_results(self, mock_process_each_record, mock_calculate_gen_token_speed_latency, \
        mock_calculate_req_latency, mock_calculate_first_token_latency):
        data = {'batch_type': ['Prefill', 'Decode', 'Decode'],
                'name': ['httpRes', 'httpRes', 'httpRes'],
                'end_datetime': ['2020-01-01', '2020-01-02', '2020-01-03'],
                'rid_list': [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9']],
                'token_id_list': [['0', '0', '0'], ['4', '5', '6'], ['7', '8', '9']]}
        df = pd.DataFrame(data)

        # 设置模拟函数的返回值
        mock_calculate_first_token_latency.return_value = (100, 100, 100, 100)
        mock_calculate_req_latency.return_value = (200, 200, 200, 200)
        mock_calculate_gen_token_speed_latency.return_value = (300, 300, 300, 300)

        # 调用函数
        first_token_latency_views, req_latency_views, prefill_gen_speed_views, \
            decode_gen_speed_views = gen_exporter_results(df)

        # 检查结果
        self.assertEqual(len(first_token_latency_views), 1)
        self.assertEqual(len(req_latency_views), 3)
        self.assertEqual(len(prefill_gen_speed_views), 1)
        self.assertEqual(len(decode_gen_speed_views), 2)

        # 检查模拟函数是否被正确调用
        mock_process_each_record.assert_called()
        mock_calculate_first_token_latency.assert_called()
        mock_calculate_req_latency.assert_called()
        mock_calculate_gen_token_speed_latency.assert_called()


    @patch.object(ExporterLatency, 'get_err_log_flag')
    @patch.object(ExporterLatency, 'set_err_log_flag')
    @patch('ms_service_profiler.exporters.exporter_latency.logger')
    def test_print_warning_log_no_error(self, mock_logger, mock_set_err_log_flag, mock_get_err_log_flag):
        # 测试当get_err_log_flag返回False时，是否正确地打印警告日志并设置错误日志标志
        mock_get_err_log_flag.return_value = False
        print_warning_log('test_log')
        mock_logger.warning.assert_called_once_with("The 'test_log' field info is missing, please check.")
        mock_set_err_log_flag.assert_called_once_with('test_log', True)
