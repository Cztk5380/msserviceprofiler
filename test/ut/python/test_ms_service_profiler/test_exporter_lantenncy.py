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

import argparse
import unittest
from unittest.mock import patch
import pandas as pd
from ms_service_profiler.exporters.exporter_latency import ExporterLatency, TimeIntervalConfig
from ms_service_profiler.exporters.exporter_summary import (
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


    @patch('ms_service_profiler.exporters.exporter_summary.process_each_record')
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


class TestExporterLatencyMethods(unittest.TestCase):
    """测试 ExporterLatency 类的各个计算方法"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.test_data = {
            'rid': [1, 2, 3, 4, 5],
            'start_time': [1000, 2000, 3000, 4000, 5000],
            'end_time': [1500, 2500, 3500, 4500, 5500],
            'event': ['httpReq', 'httpReq', 'httpReq', 'httpReq', 'httpReq'],
            'iter': [0, 0, 0, 0, 0],
            'batch_size': [10, 20, 30, 40, 50]
        }
    
    # 测试用例 1: 基础统计计算
    def test_calculate_all_statistics_empty_series(self):
        """测试空数据系列的统计计算"""
        result = ExporterLatency._calculate_all_statistics([])
        self.assertIsNone(result)
    
    def test_calculate_all_statistics_single_value(self):
        """测试单个值的统计计算"""
        result = ExporterLatency._calculate_all_statistics([100])
        self.assertEqual(result['min_value'], 100)
        self.assertEqual(result['max_value'], 100)
        self.assertEqual(result['avg'], 100)
        self.assertEqual(result['p50'], 100)
        self.assertEqual(result['p90'], 100)
        self.assertEqual(result['p99'], 100)
    
    def test_calculate_all_statistics_normal_case(self):
        """测试正常数据系列的统计计算"""
        data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        result = ExporterLatency._calculate_all_statistics(data)
        self.assertEqual(result['min_value'], 10)
        self.assertEqual(result['max_value'], 100)
        self.assertEqual(result['avg'], 55.0)
        self.assertEqual(result['p50'], 55.0)
        self.assertAlmostEqual(result['p90'], 91.0, places=1)
    
    # 测试用例 2: 按字段计算统计值
    def test_calculate_statistics_with_fields_partial(self):
        """测试只返回指定字段的统计计算"""
        data = [10, 20, 30, 40, 50]
        result = ExporterLatency._calculate_statistics_with_fields(
            data, 
            ['p50', 'avg']
        )
        self.assertEqual(len(result), 2)
        self.assertIn('p50', result)
        self.assertIn('avg', result)
        self.assertNotIn('p99', result)
    
    def test_calculate_statistics_with_fields_global_stats(self):
        """测试包含全局统计值的计算"""
        data = [10, 20, 30, 40, 50]
        global_stats = {'global_p50': 25.0, 'global_avg': 30.0}
        result = ExporterLatency._calculate_statistics_with_fields(
            data,
            ['p50', 'avg'],
            global_stats
        )
        self.assertIn('global_p50', result)
        self.assertIn('global_avg', result)
        self.assertEqual(result['global_p50'], 25.0)
    
    # 测试用例 3: 时间窗口分组
    def test_group_by_time_intervals_empty_dataframe(self):
        """测试空DataFrame的时间窗口分组"""
        df = pd.DataFrame()
        config = TimeIntervalConfig()
        result = ExporterLatency._group_by_time_intervals(
            df, 'start_time', 'value', config
        )
        self.assertEqual(result, [])
    
    def test_group_by_time_intervals_single_window(self):
        """测试单时间窗口的数据分组"""
        df = pd.DataFrame({
            'timestamp': [1000, 2000, 3000, 4000],
            'value': [10, 20, 30, 40]
        })
        config = TimeIntervalConfig(
            time_interval_us=5000,
            required_stats_fields=['avg', 'p50']
        )
        result = ExporterLatency._group_by_time_intervals(
            df, 'timestamp', 'value', config
        )
        self.assertEqual(len(result), 1)
        self.assertIn('timestamp', result[0])
        self.assertIn('avg', result[0])
    
    def test_group_by_time_intervals_multiple_windows(self):
        """测试多时间窗口的数据分组"""
        df = pd.DataFrame({
            'timestamp': [1000, 6000, 11000, 16000],
            'value': [10, 20, 30, 40]
        })
        config = TimeIntervalConfig(
            time_interval_us=5000,
            required_stats_fields=['avg', 'p50', 'p99']
        )
        result = ExporterLatency._group_by_time_intervals(
            df, 'timestamp', 'value', config
        )
        self.assertGreater(len(result), 1)
    
    def test_gen_exporter_req_latency_views_valid_events(self):
        """测试有效事件序列的请求延迟计算"""
        df = pd.DataFrame({
            'rid': [1, 1, 1],
            'start_time': [1000, 2000, 3000],
            'end_time': [1500, 2500, 3500],
            'event': ['httpReq', 'httpRes', 'FINISHED']
        })
        result = ExporterLatency.gen_exporter_req_latency_views(df)
        self.assertGreater(len(result), 0)
    
    # 测试用例 5: 首token延迟视图生成
    def test_gen_exporter_first_token_latency_views_empty_data(self):
        """测试空数据的首token延迟视图生成"""
        df = pd.DataFrame()
        result = ExporterLatency.gen_exporter_first_token_latency_views(df)
        self.assertEqual(result, [])
    
    def test_gen_exporter_first_token_latency_views_valid_data(self):
        """测试有效数据的首token延迟计算"""
        df = pd.DataFrame({
            'start_time': [1000, 2000, 3000, 4000, 5000],
            'ttft': [100, 150, 200, 180, 220]
        })
        result = ExporterLatency.gen_exporter_first_token_latency_views(df)
        self.assertGreater(len(result), 0)
    
    # 测试用例 6: 预填充生成速度计算
    def test_calculate_prefill_speed_logic_no_batch_schedule(self):
        """测试没有BatchSchedule事件时的预填充速度计算"""
        df = pd.DataFrame({
            'event': ['Execute', 'Execute'],
            'iter': [0, 1],
            'start_time': [1000, 2000],
            'end_time': [1500, 2500],
            'batch_size': [10, 10]
        })
        result = ExporterLatency._calculate_prefill_speed_logic(df, rid=1)
        self.assertEqual(len(result), 0)
    
    def test_calculate_prefill_speed_logic_no_execute(self):
        """测试没有Execute事件时的预填充速度计算"""
        df = pd.DataFrame({
            'event': ['BatchSchedule'],
            'iter': [0],
            'start_time': [1000],
            'end_time': [1500],
            'batch_size': [10]
        })
        result = ExporterLatency._calculate_prefill_speed_logic(df, rid=1)
        self.assertEqual(len(result), 0)
    
    def test_calculate_prefill_speed_logic_valid_events(self):
        """测试有效事件的预填充速度计算"""
        df = pd.DataFrame({
            'event': ['BatchSchedule', 'Execute'],
            'iter': [0, 0],
            'start_time': [1000, 2000],
            'end_time': [1500, 2500],
            'batch_size': [10, 10]
        })
        result = ExporterLatency._calculate_prefill_speed_logic(df, rid=1)
        self.assertEqual(len(result), 1)
        self.assertIn('prefill_gen_speed', result[0])
    
    # 测试用例 7: 解码生成速度计算
    def test_calculate_decode_speed_logic_non_consecutive_iters(self):
        """测试非连续iter的解码速度计算"""
        df = pd.DataFrame({
            'event': ['Execute', 'Execute'],
            'iter': [0, 2],  # 不连续
            'start_time': [1000, 2000],
            'end_time': [1500, 2500],
            'batch_size': [10, 10]
        })
        result = ExporterLatency._calculate_decode_speed_logic(df, rid=1)
        self.assertEqual(len(result), 0)
    
    def test_calculate_decode_speed_logic_valid_consecutive_iters(self):
        """测试连续iter的解码速度计算"""
        df = pd.DataFrame({
            'event': ['Execute', 'Execute', 'Execute'],
            'iter': [0, 1, 2],
            'start_time': [1000, 2000, 3000],
            'end_time': [1500, 2500, 3500],
            'batch_size': [10, 10, 10]
        })
        result = ExporterLatency._calculate_decode_speed_logic(df, rid=1)
        # 应该有两个速度计算结果 (1-0 和 2-1)
        self.assertEqual(len(result), 2)
    
    # 测试用例 8: 生成速度通用计算
    def test_calculate_speed_from_events_empty_data(self):
        """测试空数据的生成速度计算"""
        df = pd.DataFrame()
        
        def event_filter(df):
            return df["event"].isin(["Execute"])
        
        result = ExporterLatency._calculate_speed_from_events(
            df, event_filter, lambda x, y: []
        )
        self.assertEqual(result, [])
    
    def test_calculate_speed_from_events_with_mock_logic(self):
        """测试使用模拟逻辑的生成速度计算"""
        df = pd.DataFrame({
            'rid': [1, 1, 2, 2],
            'event': ['Execute', 'Execute', 'Execute', 'Execute'],
            'iter': [0, 1, 0, 1],
            'start_time': [1000, 2000, 3000, 4000],
            'end_time': [1500, 2500, 3500, 4500],
            'batch_size': [10, 10, 20, 20]
        })
        
        def event_filter(df):
            return df["event"].isin(["Execute"])
        
        def mock_logic(group, rid):
            return [{'timestamp_numeric': 1000, 'speed': 100}]
        
        result = ExporterLatency._calculate_speed_from_events(
            df, event_filter, mock_logic
        )
        self.assertGreater(len(result), 0)
    
    # 测试用例 9: 百分位数视图生成
    def test_gen_exporter_percentile_of_df_empty_data(self):
        """测试空DataFrame的百分位数视图生成"""
        df = pd.DataFrame()
        result = ExporterLatency.gen_exporter_percentile_of_df(
            df, 'timestamp', 'value'
        )
        self.assertEqual(result, [])
    
    def test_gen_exporter_percentile_of_df_missing_columns(self):
        """测试缺少必要列的百分位数视图生成"""
        df = pd.DataFrame({'value': [1, 2, 3]})
        result = ExporterLatency.gen_exporter_percentile_of_df(
            df, 'timestamp', 'value'
        )
        self.assertEqual(result, [])
    
    def test_gen_exporter_percentile_of_df_with_max_points(self):
        """测试限制最大点数的百分位数视图生成"""
        df = pd.DataFrame({
            'timestamp': list(range(100)),
            'value': list(range(100))
        })
        result = ExporterLatency.gen_exporter_percentile_of_df(
            df, 'timestamp', 'value', max_points=10
        )
        # 结果点数应该接近max_points
        self.assertLessEqual(len(result), 10)
    
    # 测试用例 10: 导出器初始化
    def test_initialize_with_args(self):
        """测试导出器初始化"""
        args = argparse.Namespace(format=['db'])
        ExporterLatency.initialize(args)
        self.assertEqual(ExporterLatency.args.format, ['db'])
    
    # 测试用例 11: 错误日志设置
    def test_set_and_get_err_log_flag(self):
        """测试错误日志标志的设置和获取"""
        ExporterLatency.set_err_log_flag('start_time', True)
        flag = ExporterLatency.get_err_log_flag('start_time')
        self.assertTrue(flag)
        
        ExporterLatency.set_err_log_flag('start_time', False)
        flag = ExporterLatency.get_err_log_flag('start_time')
        self.assertFalse(flag)
    
    # 测试用例 12: 导出功能（模拟测试）
    @patch('ms_service_profiler.exporters.exporter_latency.write_result_to_db')
    @patch('ms_service_profiler.exporters.exporter_latency.check_domain_valid')
    def test_export_with_db_format(self, mock_check_domain, mock_write_db):
        """测试数据库格式的导出功能"""
        # 模拟数据
        mock_check_domain.return_value = True
        data = {
            'tx_data_df': pd.DataFrame({'domain': ['ModelExecute', 'BatchSchedule']}),
            'req_ttft_df': pd.DataFrame({'start_time': [1000], 'ttft': [100]}),
            'req_event_df': pd.DataFrame({
                'rid': [1],
                'start_time': [1000],
                'end_time': [2000],
                'event': ['httpReq']
            })
        }
        
        # 调用导出方法
        args = argparse.Namespace(format=['db'])
        ExporterLatency.initialize(args)
        ExporterLatency.export(data)
        
        # 验证函数调用
        mock_check_domain.assert_called_once()
        mock_write_db.assert_called()
    
    @patch('ms_service_profiler.exporters.exporter_latency.write_result_to_db')
    @patch('ms_service_profiler.exporters.exporter_latency.check_domain_valid')
    def test_export_without_db_format(self, mock_check_domain, mock_write_db):
        """测试非数据库格式的导出功能"""
        args = argparse.Namespace(format=['csv'])
        ExporterLatency.initialize(args)
        data = {'tx_data_df': pd.DataFrame()}
        
        ExporterLatency.export(data)
        
        # 应该不调用任何数据库相关函数
        mock_check_domain.assert_not_called()
        mock_write_db.assert_not_called()
    
    @patch('ms_service_profiler.exporters.exporter_latency.write_result_to_db')
    @patch('ms_service_profiler.exporters.exporter_latency.check_domain_valid')
    def test_export_invalid_domain(self, mock_check_domain, mock_write_db):
        """测试无效域名的导出功能"""
        mock_check_domain.return_value = False
        data = {
            'tx_data_df': pd.DataFrame({'domain': ['InvalidDomain']})
        }
        
        args = argparse.Namespace(format=['db'])
        ExporterLatency.initialize(args)
        ExporterLatency.export(data)
        
        # 验证函数调用
        mock_check_domain.assert_called_once()
        mock_write_db.assert_not_called()


class TestTimeIntervalConfig(unittest.TestCase):
    """测试 TimeIntervalConfig 配置类"""
    
    def test_default_initialization(self):
        """测试默认初始化"""
        config = TimeIntervalConfig()
        self.assertEqual(config.time_interval_us, 100000)
        self.assertEqual(config.required_stats_fields, 
                        ['p50', 'p90', 'p99', 'avg', 'min_value', 'max_value'])
        self.assertFalse(config.include_global_stats)
    
    def test_custom_initialization(self):
        """测试自定义初始化"""
        config = TimeIntervalConfig(
            time_interval_us=50000,
            required_stats_fields=['p50', 'avg'],
            include_global_stats=True
        )
        self.assertEqual(config.time_interval_us, 50000)
        self.assertEqual(config.required_stats_fields, ['p50', 'avg'])
        self.assertTrue(config.include_global_stats)
    
    def test_post_init_default_fields(self):
        """测试后初始化默认字段设置"""
        config = TimeIntervalConfig(required_stats_fields=None)
        # __post_init__ 应该设置默认字段
        self.assertEqual(config.required_stats_fields, 
                        ['p50', 'p90', 'p99', 'avg', 'min_value', 'max_value'])