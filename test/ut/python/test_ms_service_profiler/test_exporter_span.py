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
import os
import pytest
from pathlib import Path
import shutil
from unittest.mock import patch, MagicMock

import pandas as pd


from ms_service_profiler.exporters.exporter_span import (
    ExporterSpan,
    get_filter_span_df
)


class TestExporterSpan:

    @pytest.fixture
    def test_path(self):
        """创建测试路径"""
        path = os.path.join(os.getcwd(), "output_test_span")
        yield path
        if os.path.exists(path):
            shutil.rmtree(path)

    @pytest.fixture
    def args(self, test_path):
        """创建测试参数"""
        return type('Args', (object,), {
            'output_path': test_path,
            'format': ['csv'],
            'span': ['forward']
        })

    @pytest.fixture
    def sample_tx_data_df(self):
        """创建示例 tx_data_df 数据"""
        data = {
            'name': ['forward', 'batchFrameworkProcessing', 'forward', 'batchschedule'],
            'start_time': [1000, 2000, 3000, 4000],
            'end_time': [1500, 2500, 3500, 4500],
            'during_time': [500, 500, 500, 500],
            'hostname': ['localhost', 'localhost', 'localhost', 'localhost'],
            'pid': [0, 0, 1, 1],
            'args': ['{"rid": "cmpl-123"}', '{"rid": "cmpl-456"}', '{"rid": "cmpl-789"}', '{}']
        }
        return pd.DataFrame(data)

    @pytest.fixture
    def sample_tx_data_df_missing_columns(self):
        """创建缺失列的示例数据"""
        data = {
            'name': ['forward', 'batchFrameworkProcessing'],
            'start_time': [1000, 2000],
            'end_time': [1500, 2500],
        }
        return pd.DataFrame(data)

    def test_initialize(self, args):
        """测试初始化"""
        ExporterSpan.initialize(args)
        assert ExporterSpan.args == args

    def test_get_span_names_with_args(self, args):
        """测试获取span名称（带参数）"""
        ExporterSpan.initialize(args)
        span_names = ExporterSpan._get_span_names()
        assert 'forward' in span_names
        assert 'batchFrameworkProcessing' in span_names
        assert 'BatchSchedule' in span_names

    def test_get_span_names_without_args(self):
        """测试获取span名称（无参数）"""
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': None})
        ExporterSpan.initialize(args)
        span_names = ExporterSpan._get_span_names()
        assert 'forward' in span_names
        assert 'BatchSchedule' in span_names
        assert 'batchFrameworkProcessing' in span_names

    def test_prepare_span_data(self, sample_tx_data_df):
        """测试准备span数据"""
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': ['forward']})
        ExporterSpan.initialize(args)
        result = ExporterSpan._prepare_span_data(sample_tx_data_df)
        assert not result.empty
        assert 'forward' in result['name'].values

    def test_export_with_none_data(self, args):
        """测试导出空数据"""
        data = {'tx_data_df': None}
        ExporterSpan.initialize(args)
        with patch('ms_service_profiler.exporters.exporter_span.logger') as mock_logger:
            ExporterSpan.export(data)
            mock_logger.warning.assert_called_once()

    def test_export_with_empty_df(self, args):
        """测试导出空DataFrame"""
        data = {'tx_data_df': pd.DataFrame(columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])}
        ExporterSpan.initialize(args)
        with patch('ms_service_profiler.exporters.exporter_span.get_filter_span_df') as mock_filter:
            mock_filter.return_value = pd.DataFrame(columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])
            with patch('ms_service_profiler.exporters.exporter_span.logger') as mock_logger:
                ExporterSpan.export(data)
                mock_logger.warning.assert_called()


class TestGetFilterSpanDf:

    @pytest.fixture
    def sample_df(self):
        """创建示例DataFrame"""
        data = {
            'name': ['forward', 'batchFrameworkProcessing', 'other'],
            'start_time': ['1000', '2000', '3000'],
            'end_time': ['1500', '2500', '3500'],
            'during_time': ['500', '500', '500'],
            'hostname': ['localhost', 'localhost', 'localhost'],
            'pid': [0, 0, 1],
            'args': ['{}', '{}', '{}']
        }
        return pd.DataFrame(data)

    def test_get_filter_span_df_integration(self, sample_df):
        """测试get_filter_span_df集成"""
        required_columns = ['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid']
        result = get_filter_span_df(sample_df, required_columns, time_columns=['start_time', 'end_time', 'during_time'])
        assert not result.empty
        assert list(result.columns) == required_columns
        assert result['start_time'].dtype == 'float64'
        assert result['end_time'].dtype == 'float64'
        assert result['during_time'].dtype == 'float64'

    def test_get_filter_span_df_missing_columns(self, sample_df):
        """测试get_filter_span_df处理缺失列"""
        required_columns = ['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'missing_col']
        result = get_filter_span_df(sample_df, required_columns)
        assert not result.empty
        assert list(result.columns) == required_columns
        assert 'missing_col' in result.columns
        assert result['missing_col'].isna().all()
