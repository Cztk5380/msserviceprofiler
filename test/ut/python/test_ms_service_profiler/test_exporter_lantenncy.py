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
import argparse
import unittest
from unittest.mock import patch
from unittest.mock import ANY
import numpy as np
import pandas as pd
from ms_service_profiler.exporters.exporter_latency import ExporterLatency
from ms_service_profiler.ms_service_profiler_ext.exporters.exporter_summary import (
    process_each_record,
    gen_exporter_results,
    print_warning_log,
)


class TestTimestampConverter(unittest.TestCase):
    def test_process_each_record_request(self):
        req_map = {}
        batch_map = {}
        record = {'name': 'httpReq', 'rid': '1', 'start_time': '1577836800000000', \
                  'rid_list': None, 'token_id_list': None, 'end_time': '1577836800001000'}
        process_each_record(req_map, batch_map, record)

    def test_process_each_record_response(self):
        req_map = {'1': {'start_time': '1577836800000000', 'httpReq_start': '123', 'token_id': '1'}}
        batch_map = {}
        record = {'name': 'httpRes', 'rid': '1', 'end_time': '1577836800001000', \
                  'rid_list': None, 'token_id_list': None}
        process_each_record(req_map, batch_map, record)

    def test_process_each_record_first_token_latency(self):
        req_map = {'1': {'start_time': '1577836800000000', 'token_id': {'1': '0', '0': '-1'}, 'end_time': '11',
                         'req_exec_time': '12', 'httpReq_start': '1'}}
        batch_map = {}
        record = {'name': 'modeExec', 'rid': '1', 'end_time': '1577836800001000', 'during_time': 10, \
                  'rid_list': ['1'], 'token_id_list': [0], 'batch_type': 'Prefill'}
        process_each_record(req_map, batch_map, record)
        if 'first_token_latency' in req_map['1']:
            self.assertEqual(req_map['1']['first_token_latency'], 10)
        else:
            raise KeyError("Key 'first_token_latency' does not exist in req_map.")

    def test_process_each_record_prefill_token_num(self):
        req_map = {'1': {'start_time': '1577836800000000', 'token_id': {'1': '0', '0': '-1'}, 'end_time': '11',
                         'req_exec_time': '12', 'httpReq_start': '1'}}
        batch_map = {}
        record = {'name': 'modeExec', 'rid': '1', 'end_time': '1577836800001000', 'during_time': 10, \
                  'rid_list': ['1'], 'token_id_list': [0], 'batch_type': 'Prefill'}
        process_each_record(req_map, batch_map, record)

    def test_get_empty_metric_percentile_results(self):
        self.assertEqual(ExporterLatency._calculate_all_statistics([]), None)

    def test_get_single_metric_percentile_results(self):
        metric = [10]
        avg, p50, p90, p99 = ExporterLatency._calculate_all_statistics(metric).get('avg'), \
                             ExporterLatency._calculate_all_statistics(metric).get('p50'), \
                             ExporterLatency._calculate_all_statistics(metric).get('p90'), \
                             ExporterLatency._calculate_all_statistics(metric).get('p99')
        self.assertEqual(avg, 10.0)
        self.assertEqual(p50, 10.0)
        self.assertEqual(p90, 10.0)
        self.assertEqual(p99, 10.0)

    def test_get_multiple_metrics_percentile_results(self):
        metric = [10, 20, 30, 40, 50]
        avg, p50, p90, p99 = ExporterLatency._calculate_all_statistics(metric).get('avg'), \
                             ExporterLatency._calculate_all_statistics(metric).get('p50'), \
                             ExporterLatency._calculate_all_statistics(metric).get('p90'), \
                             ExporterLatency._calculate_all_statistics(metric).get('p99')
        self.assertEqual(avg, 30.0)
        self.assertEqual(p50, 30.0)
        self.assertEqual(p90, 46.0)
        self.assertEqual(p99, 49.6)


    def test_calculate_req_latency_multiple_reqs(self):
        req_map = {
            '1': {'start_time': 10, 'end_time': 20},
            '2': {'start_time': 15, 'end_time': 25},
            '3': {'start_time': 20, 'end_time': 30},
            '4': {'start_time': 25, 'end_time': 35},
            '5': {'start_time': 30, 'end_time': 40}
        }


    @patch('ms_service_profiler.ms_service_profiler_ext.exporters.exporter_summary.process_each_record')
    def test_gen_exporter_results(self, mock_process_each_record):
        data = {'batch_type': ['Prefill', 'Decode', 'Decode'],
                'name': ['httpRes', 'httpRes', 'httpRes'],
                'end_datetime': ['2020-01-01', '2020-01-02', '2020-01-03'],
                'rid_list': [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9']],
                'token_id_list': [['0', '0', '0'], ['4', '5', '6'], ['7', '8', '9']]}
        df = pd.DataFrame(data)

        # 调用函数
        req_stats, batch_status, total_map = gen_exporter_results(df)

        # 检查结果
        self.assertEqual(len(req_stats), 7)
        self.assertEqual(len(batch_status), 4)
        self.assertEqual(len(total_map), 4)

        # 检查模拟函数是否被正确调用
        mock_process_each_record.assert_called()

    @patch.object(ExporterLatency, 'get_err_log_flag')
    @patch.object(ExporterLatency, 'set_err_log_flag')
    @patch('ms_service_profiler.exporters.exporter_latency.logger')
    def test_print_warning_log_no_error(self, mock_logger, mock_set_err_log_flag, mock_get_err_log_flag):
        # 测试当get_err_log_flag返回False时，是否正确地打印警告日志并设置错误日志标志
        mock_get_err_log_flag.return_value = False
        print_warning_log('start_time')