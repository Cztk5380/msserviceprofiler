# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from unittest import mock
import json
import threading
import tempfile
import os
import math

import pytest
import pandas as pd

from ms_service_profiler.exporters.exporter_trace import ExporterTrace, write_trace_data_to_file, \
    save_trace_data_into_json, add_flow_event, create_trace_events, sort_trace_events_by_tid, add_mem_events


# Mock 数据
@pytest.fixture
def mock_data():
    # 模拟输入的 DataFrame 数据
    return {
        'tx_data_df': pd.DataFrame({
            'name': ['task1', 'task2'],
            'domain': ['domain1', 'domain2'],
            'start_time': [12345, 12346],
            'end_time': [12355, 12356],
            'during_time': [10, 10],
            'start_datetime': [12345, 12346],
            'end_datetime': [12345, 12346],
            'batch_type': ['batch1', 'batch2'],
            'batch_size': [5, 10],
            'deviceBlock=': [5, 10],
            'res_list': [['res1'], ['res2']],
            'rid': [[0], [1]],
            'pid': [[0], [1]]
        }),
        'cpu_data_df': pd.DataFrame({
            'start_time': [12345, 12346],
            'start_datetime': [12345, 12346],
            'usage': [30.5, 35.0]
        }),
        'memory_data_df': pd.DataFrame({
            'start_time': [12345, 12346],
            'start_datetime': [12345, 12346],
            'usage': [200, 250]
        })
    }


# 测试 ExporterTrace 初始化
def test_exporter_initialize():
    mock_args = mock.Mock()
    ExporterTrace.initialize(mock_args)
    assert ExporterTrace.args == mock_args


# 测试 ExporterTrace 的 export 方法
@mock.patch('ms_service_profiler.exporters.exporter_trace.create_trace_events')
@mock.patch('ms_service_profiler.exporters.exporter_trace.save_trace_data_into_json')
def test_exporter_export(mock_save, mock_create, mock_data):
    # 模拟 create_trace_events 返回值
    mock_create.return_value = {'traceEvents': []}
    mock_save.return_value = None  # 模拟保存行为

    ExporterTrace.initialize(mock.Mock(output_path='/tmp'))
    ExporterTrace.export(mock_data)

    # 检查创建 trace 事件的函数是否被调用
    mock_create.assert_called_once_with(
        mock_data['tx_data_df'], mock_data['cpu_data_df'], mock_data['memory_data_df'])

    # 检查保存 trace 数据的函数是否被调用
    mock_save.assert_called_once()


def test_write_trace_data_to_file():
    trace_data = {'traceEvents': []}

    with tempfile.TemporaryDirectory() as temp_dir:
        output = os.path.join(temp_dir, 'trace.json')

        write_trace_data_to_file(trace_data, output)
        assert os.path.exists(output)  # 验证文件是否存在


def test_create_trace_events(mock_data):

    result = create_trace_events(
        mock_data['tx_data_df'], mock_data['cpu_data_df'], mock_data['memory_data_df']
    )

    assert 'traceEvents' in result
    assert len(result['traceEvents']) > 0
    assert all('name' in event for event in result['traceEvents'])


# 测试 sort_trace_events_by_tid
def test_sort_trace_events_by_tid():
    trace_events = [
        {'tid': 'http', 'name': 'event1'},
        {'tid': 'Queue', 'name': 'event2'},
        {'tid': 'BatchSchedule', 'name': 'event3'}
    ]
    sorted_trace_events = sort_trace_events_by_tid(trace_events)

    # 验证事件是否按正确顺序排序
    assert sorted_trace_events[0]['tid'] == 'http'
    assert sorted_trace_events[1]['tid'] == 'Queue'
    assert sorted_trace_events[2]['tid'] == 'BatchSchedule'


def test_add_mem_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, 0.75, 0.25],
    }
    df = pd.DataFrame(data)

    result = add_mem_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'Memory Usage'
    assert result[0]['args'] == {'Memory Usage': 0.5}
    assert result[1]['args'] == {'Memory Usage': 0.75}
    assert result[2]['args'] == {'Memory Usage': 0.25}


def test_add_mem_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'usage'])  # 没有数据的 DataFrame

    result = add_mem_events(df)

    assert result == []  # 应该返回空列表


def test_add_mem_events_none_input():
    # 输入为 None
    result = add_mem_events(None)

    assert result == []  # 应该返回空列表


def test_add_mem_events_with_missing_data():
    # DataFrame 中的 usage 列存在缺失值
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, None, 0.25],  # 包含 None
    }
    df = pd.DataFrame(data)

    result = add_mem_events(df)

    assert len(result) == 3
    assert math.isnan(result[1]['args']['Memory Usage'])


def test_add_mem_events_with_nan_data():
    #  DataFrame 中的 usage 列包含 NaN
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, float('nan'), 0.25],  # 包含 NaN
    }
    df = pd.DataFrame(data)

    result = add_mem_events(df)

    assert len(result) == 3  # 应该有 3 个事件
    assert math.isnan(result[1]['args']['Memory Usage'])
