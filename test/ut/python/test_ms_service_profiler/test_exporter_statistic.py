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

import logging
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from ms_service_profiler.exporters.exporter_statistic import (
    ExporterStatistic,
    calculate_stats,
    TOP_N_REQUESTS,
    HORIZONTAL_TABLE_WIDTH,
    FIRST_COLUMN_WIDTH,
    DEFAULT_STATISTIC_SPAN,
    REQUEST_STATISTIC_SPANS,
    BUBBLE_SPAN_NAME
)


class TestCalculateStats:

    @pytest.fixture
    def sample_series(self):
        """创建示例数据序列"""
        return pd.Series([10, 20, 30, 40, 50])

    def test_calculate_stats_basic(self, sample_series):
        """测试基本统计计算"""
        result = calculate_stats(sample_series)
        assert result['min'] == 10
        assert result['max'] == 50
        assert result['avg'] == 30
        assert result['P50'] == 30
        assert result['P90'] == 46
        assert result['total'] == 150

    def test_calculate_stats_single_value(self):
        """测试单个值"""
        series = pd.Series([100])
        result = calculate_stats(series)
        assert result['min'] == 100
        assert result['max'] == 100
        assert result['avg'] == 100


class TestPrintStatistics:

    def test_print_statistics_horizontal(self, capsys):
        """测试横向打印"""
        data_list = [
            {'name': 'test1', 'stats': {'min': 10, 'avg': 20, 'P50': 20, 'P90': 30, 'P99': 35, 'max': 40, 'total': 100}}
        ]
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': None})
        ExporterStatistic.initialize(args)
        ExporterStatistic.print_statistics(data_list, print_header_label='Test')
        captured = capsys.readouterr()
        assert 'Test' in captured.out


class TestExporterStatistic:

    @pytest.fixture
    def args(self):
        """创建测试参数"""
        return type('Args', (object,), {
            'output_path': '/tmp',
            'format': ['csv'],
            'span': ['forward']
        })

    @pytest.fixture
    def sample_tx_data_df(self):
        """创建示例 tx_data_df 数据"""
        data = {
            'name': ['forward', 'batchFrameworkProcessing', 'forward'],
            'start_time': [1000, 2000, 3000],
            'end_time': [1500, 2500, 3500],
            'during_time': [500, 500, 500],
            'hostname': ['localhost', 'localhost', 'localhost'],
            'pid': [0, 0, 1],
            'args': ['{"rid": "cmpl-123"}', '{"rid": "cmpl-456"}', '{"rid": "cmpl-789"}']
        }
        return pd.DataFrame(data)

    def test_initialize(self, args):
        """测试初始化"""
        ExporterStatistic.initialize(args)
        assert ExporterStatistic.args == args

    def test_get_span_names_with_args(self, args):
        """测试获取span名称（带参数）"""
        ExporterStatistic.initialize(args)
        span_names = ExporterStatistic._get_span_names()
        assert 'forward' in span_names
        assert 'batchFrameworkProcessing' in span_names

    def test_get_span_names_without_args(self):
        """测试获取span名称（无参数）"""
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': None})
        ExporterStatistic.initialize(args)
        span_names = ExporterStatistic._get_span_names()
        assert 'forward' in span_names
        assert 'BatchSchedule' in span_names  # 注意大小写
        assert 'batchFrameworkProcessing' in span_names

    def test_export_with_none_data(self, args):
        """测试导出空数据"""
        data = {'tx_data_df': None}
        ExporterStatistic.initialize(args)
        with patch('ms_service_profiler.exporters.exporter_statistic.logger') as mock_logger:
            ExporterStatistic.export(data)
            mock_logger.warning.assert_called_once()

    def test_export_with_empty_df(self, args):
        """测试导出空DataFrame"""
        data = {'tx_data_df': pd.DataFrame(
            columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])}
        ExporterStatistic.initialize(args)
        with patch('ms_service_profiler.exporters.exporter_statistic.get_filter_span_df') as mock_filter:
            mock_filter.return_value = pd.DataFrame(
                columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])
            with patch('ms_service_profiler.exporters.exporter_statistic.logger') as mock_logger:
                ExporterStatistic.export(data)
                mock_logger.warning.assert_called()

    def test_prepare_span_data(self, sample_tx_data_df):
        """测试准备span数据"""
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': ['forward']})
        ExporterStatistic.initialize(args)
        result = ExporterStatistic._prepare_span_data(sample_tx_data_df)
        assert not result.empty
        assert 'forward' in result['name'].values

    def test_extract_and_expand_rids(self, sample_tx_data_df):
        """测试提取并展开rid"""
        # 添加rid列到测试数据
        sample_tx_data_df['rid'] = ['cmpl-123', 'cmpl-456', 'cmpl-789']
        result = ExporterStatistic._prepare_and_expand_rids(sample_tx_data_df, ['forward'])
        assert 'rid' in result.columns
        assert not result['rid'].isna().all()

    def test_calculate_all_stats(self, sample_tx_data_df):
        """测试计算所有span统计"""
        sample_tx_data_df['rid'] = ['cmpl-123', 'cmpl-456', 'cmpl-789']
        result = ExporterStatistic._calculate_all_stats(sample_tx_data_df)
        assert result['name'] == 'ALL'
        assert 'stats' in result
        assert 'min' in result['stats']
        assert 'max' in result['stats']

    def test_calculate_all_stats_with_expanded_rids(self):
        """测试计算所有span统计（带展开的rid）"""
        # 创建一个span对应多个rid的测试数据
        data = {
            'name': ['forward', 'forward', 'forward'],
            'start_time': [1000, 2000, 3000],
            'end_time': [1500, 2500, 3500],
            'during_time': [500, 600, 700],
            'rid': ['cmpl-123', 'cmpl-123', 'cmpl-456']  # 一个rid对应多个span
        }
        df = pd.DataFrame(data)
        result = ExporterStatistic._calculate_all_stats(df)
        assert result['name'] == 'ALL'
        assert 'stats' in result
        # 验证统计值是否基于展开后的数据（应该是3个值：500, 600, 700）
        assert result['stats']['min'] == 500
        assert result['stats']['max'] == 700
        assert result['stats']['avg'] == 600
        assert result['stats']['total'] == 1800

    def test_get_top_rid_stats(self):
        """测试获取top rid统计"""
        rid_stats = pd.DataFrame({
            'rid': ['cmpl-123', 'cmpl-456', 'cmpl-789'],
            'avg_duration': [100, 200, 150],
            'min_duration': [50, 100, 75],
            'max_duration': [150, 300, 225],
            'total_duration': [300, 600, 450],
            'p50_duration': [100, 200, 150],
            'p90_duration': [140, 280, 210],
            'p99_duration': [148, 294, 220]
        })
        top_forward_bubble_stats = [
            {'rid': 'cmpl-456', 'avg_time': 200},
            {'rid': 'cmpl-123', 'avg_time': 100},
            {'rid': 'cmpl-789', 'avg_time': 150}
        ]
        result = ExporterStatistic._get_top_rid_stats_from_forward_bubble(rid_stats, top_forward_bubble_stats)
        assert len(result) == 3
        assert result[0]['name'] == 'cmpl-456'
        assert result[0]['stats']['avg'] == 200

    def test_calculate_bubble_times(self):
        """测试计算bubble时间 - 按(pid, rid)分组计算"""
        batch_df = pd.DataFrame({
            'pid': [0, 0, 0],
            'start_time': [1000, 3000, 5000],
            'end_time': [1500, 2500, 5500],
            'rid': ['cmpl-123', 'cmpl-123', 'cmpl-456']
        })
        result = ExporterStatistic._calculate_bubble_times(batch_df)
        assert 'all_times' in result
        assert 'rid_times' in result
        assert len(result['all_times']) == 1
        assert result['all_times'][0] == 1500
        assert result['rid_times']['cmpl-123'] == [1500]

    def test_calculate_bubble_times_with_rid_mapping(self):
        """测试计算bubble时间并关联到当前请求 - 按(pid, rid)分组计算"""
        batch_df = pd.DataFrame({
            'pid': [0, 0, 0, 0, 0],
            'start_time': [1000, 3000, 6000, 8000, 10000],
            'end_time': [1500, 2500, 6500, 8500, 10500],
            'rid': ['cmpl-123', 'cmpl-123', 'cmpl-456', 'cmpl-456', 'cmpl-789']
        })
        result = ExporterStatistic._calculate_bubble_times(batch_df)
        assert 'all_times' in result
        assert 'rid_times' in result
        assert len(result['all_times']) == 2
        assert result['all_times'][0] == 1500
        assert result['all_times'][1] == 1500
        assert result['rid_times']['cmpl-123'] == [1500]
        assert result['rid_times']['cmpl-456'] == [1500]
        assert 'cmpl-789' not in result['rid_times']

    def test_build_bubble_stats_data(self):
        """测试构建bubble统计数据"""
        bubble_data = {
            'all_times': [100, 200, 300],
            'rid_times': {
                'cmpl-123': [100, 200],
                'cmpl-456': [300]
            }
        }
        top_forward_bubble_stats = [
            {'rid': 'cmpl-123', 'avg_time': 150},
            {'rid': 'cmpl-456', 'avg_time': 300}
        ]
        result = ExporterStatistic._build_bubble_stats_data(bubble_data, top_forward_bubble_stats)
        assert len(result) == 3
        assert result[0]['name'] == 'ALL'
        assert result[0]['stats']['total'] == 600

    def test_depends(self):
        """测试依赖"""
        assert ExporterStatistic.depends() == ["pipeline:service"]

    def test_outputs(self):
        """测试输出"""
        assert ExporterStatistic.outputs() == ['statistic']


class TestExporterStatisticAdditional:

    @pytest.fixture
    def args_additional(self):
        """创建测试参数"""
        return type('Args', (object,), {
            'output_path': '/tmp',
            'format': ['csv'],
            'span': ['forward']
        })

    @pytest.fixture
    def sample_tx_data_df_additional(self):
        """创建示例 tx_data_df 数据"""
        data = {
            'name': ['forward', 'batchFrameworkProcessing', 'forward', 'BatchSchedule'],
            'start_time': [1000, 2000, 3000, 4000],
            'end_time': [1500, 2500, 3500, 4500],
            'during_time': [500, 500, 500, 500],
            'hostname': ['localhost', 'localhost', 'localhost', 'localhost'],
            'pid': [0, 0, 1, 1],
            'rid': ['cmpl-123', 'cmpl-456', 'cmpl-789', 'cmpl-123'],
            'args': ['{}'] * 4
        }
        return pd.DataFrame(data)

    def test_format_rid_column_with_list(self):
        """测试格式化rid列（列表类型）"""
        series = pd.Series([['rid1', 'rid2'], ['rid3']])
        result = ExporterStatistic._format_rid_column(series)
        assert result.iloc[0] == ['rid1', 'rid2']
        assert result.iloc[1] == ['rid3']

    def test_format_rid_column_with_string(self):
        """测试格式化rid列（字符串类型）"""
        series = pd.Series(['rid1', 'rid2,rid3', ''])
        result = ExporterStatistic._format_rid_column(series)
        assert result.iloc[0] == ['rid1']
        assert result.iloc[1] == ['rid2', 'rid3']
        assert result.iloc[2] == []

    def test_format_rid_column_with_nan(self):
        """测试格式化rid列（NaN类型）"""
        series = pd.Series([None, 'rid1', float('nan')])
        result = ExporterStatistic._format_rid_column(series)
        assert result.iloc[0] == []
        assert result.iloc[1] == ['rid1']
        assert result.iloc[2] == []

    def test_prepare_and_expand_rids_success(self, sample_tx_data_df_additional):
        """测试成功准备并展开rid数据"""
        sample_tx_data_df_additional['start_time'] = sample_tx_data_df_additional['start_time'].astype(int)
        sample_tx_data_df_additional['end_time'] = sample_tx_data_df_additional['end_time'].astype(int)
        sample_tx_data_df_additional['during_time'] = sample_tx_data_df_additional['during_time'].astype(int)
        sample_tx_data_df_additional['rid'] = sample_tx_data_df_additional['rid'].astype(str)
        result = ExporterStatistic._prepare_and_expand_rids(sample_tx_data_df_additional, ['forward'])
        assert result is not None
        assert 'rid' in result.columns

    def test_prepare_and_expand_rids_empty_result(self):
        """测试准备并展开rid数据返回空结果"""
        data = pd.DataFrame({
            'name': ['other_span'],
            'start_time': [1000],
            'end_time': [1500],
            'during_time': [500],
            'rid': ['rid1']
        })
        result = ExporterStatistic._prepare_and_expand_rids(data, ['forward'])
        assert result is None

    def test_prepare_and_expand_rids_missing_time_columns(self):
        """测试准备并展开rid数据时缺少时间列"""
        data = pd.DataFrame({
            'name': ['forward'],
            'rid': ['rid1']
        })
        result = ExporterStatistic._prepare_and_expand_rids(data, ['forward'])
        assert result is not None
        assert 'rid' in result.columns

    def test_prepare_forward_data_success(self, sample_tx_data_df_additional):
        """测试成功准备forward数据"""
        result = ExporterStatistic._prepare_forward_data(sample_tx_data_df_additional)
        assert result is not None
        assert 'rid' in result.columns
        assert len(result) > 0

    def test_prepare_forward_data_empty(self):
        """测试准备forward数据返回空"""
        data = pd.DataFrame({
            'name': ['other_span'],
            'start_time': [1000],
            'end_time': [1500],
            'during_time': [500],
            'rid': ['rid1']
        })
        with patch('ms_service_profiler.exporters.exporter_statistic.logger') as mock_logger:
            result = ExporterStatistic._prepare_forward_data(data)
            assert result is None
            mock_logger.warning.assert_called()

    def test_calculate_forward_bubble_stats_single_rid(self):
        """测试计算单个rid的forward+空泡统计"""
        forward_df = pd.DataFrame({
            'pid': [0, 0],
            'rid': ['cmpl-123', 'cmpl-123'],
            'start_time': [1000, 3000],
            'end_time': [1500, 3500],
            'during_time': [500, 500]
        })
        result = ExporterStatistic._calculate_forward_bubble_stats(forward_df)
        assert len(result) == 1
        assert result[0]['rid'] == 'cmpl-123'
        assert result[0]['avg_time'] == 2000
        assert result[0]['total_time'] == 2000

    def test_calculate_forward_bubble_stats_multiple_rids(self):
        """测试计算多个rid的forward+空泡统计"""
        forward_df = pd.DataFrame({
            'pid': [0, 0, 1, 1],
            'rid': ['cmpl-123', 'cmpl-123', 'cmpl-456', 'cmpl-456'],
            'start_time': [1000, 3000, 2000, 4000],
            'end_time': [1500, 3500, 2500, 4500],
            'during_time': [500, 500, 500, 500]
        })
        result = ExporterStatistic._calculate_forward_bubble_stats(forward_df)
        assert len(result) == 2
        assert result[0]['rid'] in ['cmpl-123', 'cmpl-456']
        assert result[1]['rid'] in ['cmpl-123', 'cmpl-456']

    def test_calculate_forward_bubble_stats_empty(self):
        """测试计算forward+空泡统计（空数据）"""
        forward_df = pd.DataFrame(columns=['pid', 'rid', 'start_time', 'end_time', 'during_time'])
        result = ExporterStatistic._calculate_forward_bubble_stats(forward_df)
        assert len(result) == 0

    def test_calculate_top_forward_bubble_stats(self, sample_tx_data_df_additional):
        """测试计算top forward+空泡统计"""
        result = ExporterStatistic._calculate_top_forward_bubble_stats(sample_tx_data_df_additional)
        assert isinstance(result, list)
        assert len(result) <= TOP_N_REQUESTS

    def test_calculate_top_forward_bubble_stats_empty(self):
        """测试计算top forward+空泡统计（空数据）"""
        data = pd.DataFrame({
            'name': ['other_span'],
            'start_time': [1000],
            'end_time': [1500],
            'during_time': [500],
            'rid': ['rid1']
        })
        result = ExporterStatistic._calculate_top_forward_bubble_stats(data)
        assert len(result) == 0

    def test_print_bubble_statistics(self, sample_tx_data_df_additional, capsys):
        """测试打印bubble统计"""
        sample_tx_data_df_additional['start_time'] = sample_tx_data_df_additional['start_time'].astype(int)
        sample_tx_data_df_additional['end_time'] = sample_tx_data_df_additional['end_time'].astype(int)
        sample_tx_data_df_additional['during_time'] = sample_tx_data_df_additional['during_time'].astype(int)
        top_forward_bubble_stats = []
        ExporterStatistic._print_bubble_statistics(sample_tx_data_df_additional, top_forward_bubble_stats)

    def test_print_bubble_statistics_empty(self, capsys):
        """测试打印bubble统计（空数据）"""
        data = pd.DataFrame({
            'name': ['other_span'],
            'start_time': [1000],
            'end_time': [1500],
            'during_time': [500],
            'rid': ['rid1']
        })
        data['start_time'] = data['start_time'].astype(int)
        data['end_time'] = data['end_time'].astype(int)
        data['during_time'] = data['during_time'].astype(int)
        top_forward_bubble_stats = []
        ExporterStatistic._print_bubble_statistics(data, top_forward_bubble_stats)

    def test_export_with_exception_handling(self, args_additional, sample_tx_data_df_additional):
        """测试导出时的异常处理"""
        ExporterStatistic.initialize(args_additional)

        with patch('ms_service_profiler.exporters.exporter_statistic.calculate_stats') as mock_calc:
            mock_calc.side_effect = Exception("Test exception")

            with patch('ms_service_profiler.exporters.exporter_statistic.logger') as mock_logger:
                ExporterStatistic.export({'tx_data_df': sample_tx_data_df_additional})
                mock_logger.warning.assert_called()

    def test_constants(self):
        """测试常量值"""
        assert TOP_N_REQUESTS == 5
        assert HORIZONTAL_TABLE_WIDTH == 135
        assert FIRST_COLUMN_WIDTH == 30
        assert 'forward' in DEFAULT_STATISTIC_SPAN
        assert 'BatchSchedule' in DEFAULT_STATISTIC_SPAN
        assert 'batchFrameworkProcessing' in DEFAULT_STATISTIC_SPAN
        assert 'forward' in REQUEST_STATISTIC_SPANS
        assert BUBBLE_SPAN_NAME == ['forward']

    def test_calculate_stats_with_nan_values(self):
        """测试计算统计值（包含NaN）"""
        series = pd.Series([10, 20, float('nan'), 40, 50])
        result = calculate_stats(series)
        assert 'min' in result
        assert 'max' in result
        assert 'avg' in result

    def test_calculate_stats_with_empty_series(self):
        """测试计算统计值（空序列）"""
        series = pd.Series([])
        result = calculate_stats(series)
        assert result['min'] == 0
        assert result['max'] == 0
        assert result['avg'] == 0

    def test_calculate_stats_with_negative_values(self):
        """测试计算统计值（包含负值）"""
        series = pd.Series([-10, 0, 10, 20, 30])
        result = calculate_stats(series)
        assert result['min'] == -10
        assert result['max'] == 30
        assert result['avg'] == 10

    def test_print_statistics_with_unit_conversion(self, capsys):
        """测试打印统计信息时进行单位转换"""
        data_list = [
            {'name': 'test1',
             'stats': {'min': 1000, 'avg': 2000, 'P50': 2000, 'P90': 3000, 'P99': 3500, 'max': 4000, 'total': 10000}}
        ]
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': None})
        ExporterStatistic.initialize(args)
        ExporterStatistic.print_statistics(data_list, print_header_label='Test')
        captured = capsys.readouterr()
        assert 'Test' in captured.out
        assert 'ms' in captured.out

    def test_print_statistics_without_span_arg(self, capsys):
        """测试无span参数时的打印统计"""
        data_list = [
            {'name': 'test1', 'stats': {'min': 10, 'avg': 20, 'P50': 20, 'P90': 30, 'P99': 35, 'max': 40, 'total': 100}}
        ]
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': None})
        ExporterStatistic.initialize(args)
        ExporterStatistic.print_statistics(data_list, print_header_label='Test')
        captured = capsys.readouterr()
        assert 'Test' in captured.out

    def test_export_integration(self, args_additional, sample_tx_data_df_additional, capsys):
        """测试导出集成流程"""
        ExporterStatistic.initialize(args_additional)
        ExporterStatistic.export({'tx_data_df': sample_tx_data_df_additional})
        captured = capsys.readouterr()
        assert 'Span Statistics' in captured.out
