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
    calculate_stats
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
        data = {'tx_data_df': pd.DataFrame(columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])}
        ExporterStatistic.initialize(args)
        with patch('ms_service_profiler.exporters.exporter_statistic.get_filter_span_df') as mock_filter:
            mock_filter.return_value = pd.DataFrame(columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])
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
