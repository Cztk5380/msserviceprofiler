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
    get_filter_span_df,
    RENAME_COLUMNS,
    DEFAULT_SPAN,
    SPAN_OUTPUT_DIR
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
        data = {'tx_data_df': pd.DataFrame(
            columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])}
        ExporterSpan.initialize(args)
        with patch('ms_service_profiler.exporters.exporter_span.get_filter_span_df') as mock_filter:
            mock_filter.return_value = pd.DataFrame(
                columns=['name', 'start_time', 'end_time', 'during_time', 'hostname', 'pid', 'args'])
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


class TestExporterSpanExport:

    @pytest.fixture
    def test_path_export(self, tmpdir):
        """创建测试路径"""
        path = str(tmpdir.join("output_test_span"))
        yield path
        if os.path.exists(path):
            shutil.rmtree(path)

    @pytest.fixture
    def args_export(self, test_path_export):
        """创建测试参数"""
        return type('Args', (object,), {
            'output_path': test_path_export,
            'format': ['csv'],
            'span': ['forward']
        })

    @pytest.fixture
    def sample_tx_data_df_export(self):
        """创建示例 tx_data_df 数据"""
        data = {
            'name': ['forward', 'batchFrameworkProcessing', 'forward', 'batchschedule'],
            'start_datetime': ['2024-01-01 00:00:00.001000', '2024-01-01 00:00:00.002000',
                               '2024-01-01 00:00:00.003000', '2024-01-01 00:00:00.004000'],
            'end_datetime': ['2024-01-01 00:00:00.001500', '2024-01-01 00:00:00.002500',
                             '2024-01-01 00:00:00.003500', '2024-01-01 00:00:00.004500'],
            'during_time': [500, 500, 500, 500],
            'hostname': ['localhost', 'localhost', 'localhost', 'localhost'],
            'pid': [0, 0, 1, 1],
            'args': ['{"rid": "cmpl-123"}', '{"rid": "cmpl-456"}', '{"rid": "cmpl-789"}', '{}']
        }
        return pd.DataFrame(data)

    def test_export_span_data_creates_csv_files(self, args_export, sample_tx_data_df_export, test_path_export):
        """测试导出span数据创建CSV文件"""
        ExporterSpan.initialize(args_export)
        data = {'tx_data_df': sample_tx_data_df_export}

        ExporterSpan.export(data)

        output_dir = os.path.join(test_path_export, SPAN_OUTPUT_DIR)
        assert os.path.exists(output_dir)

        expected_files = ['forward.csv', 'batchFrameworkProcessing.csv', 'batchschedule.csv']
        for file_name in expected_files:
            file_path = os.path.join(output_dir, file_name)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                assert not df.empty
                assert 'during_time(ms)' in df.columns

    def test_export_with_unit_conversion(self, args_export, test_path_export):
        """测试导出时进行单位转换（微秒转毫秒）"""
        ExporterSpan.initialize(args_export)

        data = {'tx_data_df': pd.DataFrame({
            'name': ['forward'],
            'start_datetime': ['2024-01-01 00:00:00.001000'],
            'end_datetime': ['2024-01-01 00:00:00.001500'],
            'during_time': [500],
            'hostname': ['localhost'],
            'pid': [0],
            'args': ['{}']
        })}

        ExporterSpan.export(data)

        output_dir = os.path.join(test_path_export, SPAN_OUTPUT_DIR)
        file_path = os.path.join(output_dir, 'forward.csv')

        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            assert 'during_time(ms)' in df.columns
            assert df['during_time(ms)'].iloc[0] == 0.5

    def test_export_with_missing_spans_warning(self, args_export, sample_tx_data_df_export):
        """测试当指定的span不存在时发出警告"""
        args_export.span = ['nonexistent_span']
        ExporterSpan.initialize(args_export)

        data = {'tx_data_df': sample_tx_data_df_export}

        with patch('ms_service_profiler.exporters.exporter_span.logger') as mock_logger:
            ExporterSpan.export(data)
            mock_logger.warning.assert_called()
            warning_calls = [call for call in mock_logger.warning.call_args_list]
            assert any('nonexistent_span' in str(call) for call in warning_calls)

    def test_export_with_all_default_spans(self, test_path_export):
        """测试导出所有默认span"""
        args = type('Args', (object,), {
            'output_path': test_path_export,
            'format': ['csv'],
            'span': None
        })
        ExporterSpan.initialize(args)

        data = {'tx_data_df': pd.DataFrame({
            'name': DEFAULT_SPAN,
            'start_datetime': ['2024-01-01 00:00:00.001000'] * 3,
            'end_datetime': ['2024-01-01 00:00:00.001500'] * 3,
            'during_time': [500] * 3,
            'hostname': ['localhost'] * 3,
            'pid': [0] * 3,
            'args': ['{}'] * 3
        })}

        ExporterSpan.export(data)

        output_dir = os.path.join(test_path_export, SPAN_OUTPUT_DIR)
        assert os.path.exists(output_dir)

    def test_export_with_exception_handling(self, args_export, sample_tx_data_df_export):
        """测试异常处理"""
        ExporterSpan.initialize(args_export)

        with patch('ms_service_profiler.exporters.exporter_span.write_result_to_csv') as mock_write:
            mock_write.side_effect = Exception("Test exception")

            with patch('ms_service_profiler.exporters.exporter_span.logger') as mock_logger:
                ExporterSpan.export({'tx_data_df': sample_tx_data_df_export})
                mock_logger.warning.assert_called()

    def test_prepare_span_data_filters_by_span_names(self):
        """测试准备span数据时按span名称过滤"""
        args = type('Args', (object,), {'output_path': '/tmp', 'format': ['csv'], 'span': ['forward']})
        ExporterSpan.initialize(args)

        data = pd.DataFrame({
            'name': ['forward', 'other_span', 'forward'],
            'start_datetime': ['2024-01-01 00:00:00.001000'] * 3,
            'end_datetime': ['2024-01-01 00:00:00.001500'] * 3,
            'during_time': [500] * 3,
            'hostname': ['localhost'] * 3,
            'pid': [0] * 3,
            'args': ['{}'] * 3
        })

        result = ExporterSpan._prepare_span_data(data)
        assert not result.empty
        assert all(name in ['forward'] for name in result['name'].unique())

    def test_rename_columns_constant(self):
        """测试重命名列常量"""
        assert RENAME_COLUMNS == {
            "name": "span_name",
            "during_time": "during_time(ms)"
        }

    def test_default_span_constant(self):
        """测试默认span常量"""
        assert 'forward' in DEFAULT_SPAN
        assert 'BatchSchedule' in DEFAULT_SPAN
        assert 'batchFrameworkProcessing' in DEFAULT_SPAN

    def test_span_output_dir_constant(self):
        """测试span输出目录常量"""
        assert SPAN_OUTPUT_DIR == "span_info"

    def test_export_creates_output_directory(self, args_export, sample_tx_data_df_export, test_path_export):
        """测试导出时创建输出目录"""
        ExporterSpan.initialize(args_export)

        output_dir = os.path.join(test_path_export, SPAN_OUTPUT_DIR)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)

        data = {'tx_data_df': sample_tx_data_df_export}
        ExporterSpan.export(data)

        assert os.path.exists(output_dir)

    def test_export_with_empty_filtered_data(self, args_export, test_path_export):
        """测试过滤后数据为空的情况"""
        ExporterSpan.initialize(args_export)

        data = {'tx_data_df': pd.DataFrame({
            'name': ['other_span'],
            'start_datetime': ['2024-01-01 00:00:00.001000'],
            'end_datetime': ['2024-01-01 00:00:00.001500'],
            'during_time': [500],
            'hostname': ['localhost'],
            'pid': [0],
            'args': ['{}']
        })}

        with patch('ms_service_profiler.exporters.exporter_span.logger') as mock_logger:
            ExporterSpan.export(data)
            mock_logger.warning.assert_called()
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any('no span data after filtering' in call for call in warning_calls)
