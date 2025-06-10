# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from unittest import mock
from unittest.mock import patch, mock_open
import json
import threading
import tempfile
import os
import math

import pytest
import pandas as pd

from ms_service_profiler.utils.file_open_check import OpenException
from ms_service_profiler.exporters.exporter_trace import ExporterTrace, write_trace_data_to_file, \
    save_trace_data_into_json, add_flow_event, create_trace_events, sort_trace_events_by_tid, add_mem_events, \
    load_single_prof, find_cann_pid, merge_json_data, add_npu_events, add_kvcache_events, add_cpu_events, \
    add_pull_kvcache_events


# Mock 数据
@pytest.fixture
def mock_data():
    base_path = '/home/raonaxin/cheps/0211-1226/'

    profiles = [
        'PROF_000001_20250211122640832_MOAFENMIAMARIKCA',
        'PROF_000001_20250211122717318_QCFMCMCCQNJJGQCC',
        'PROF_000001_20250211122717318_FRPOJKFFIHHERIIA'
    ]
    date_times = [
        '20250211122801',
        '20250211122756',
        '20250211122800'
    ]

    msprof_data = []
    for profile, date_time in zip(profiles, date_times):
        file_path = f'{base_path}{profile}/mindstudio_profiler_output/msprof_{date_time}.json'
        msprof_data.append(file_path)

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
            'pid': [0, 1],
            'tid': [0, 1],
            'message': [{'rid': 0, 'PENDING+': 1, 'RUNNING+': -1, 'name': 'ReqState', 'type': 0},
                        {'rid': 1, 'PENDING+': 1, 'RUNNING+': -1, 'name': 'ReqState', 'type': 0}]
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
        }),
        'msprof_data': msprof_data
    }


@pytest.fixture
def mock_mspti():
    return {
        'api_df': pd.DataFrame({
            'name': ['aclnnInplaceCopy_SliceAiCore_Slice', 'aclnnEmbedding_GatherV2AiCore_GatherV2'],
            'start': [12345, 12346],
            'end': [12355, 12356],
            'processId': [409726, 409726],
            'threadId': [409895, 409895],
            'correlationId': [1268, 1273],
            'db_id': [409726, 409726],
        }),
        'kernel_df': pd.DataFrame({
            'name': ['aclnnInplaceCopy_SliceAiCore_Slice', 'aclnnEmbedding_GatherV2AiCore_GatherV2'],
            'type': ['KERNEL_AIVEC', 'KERNEL_AIVEC'],
            'start': [12345, 12346],
            'end': [12355, 12356],
            'deviceId': [0, 0],
            'streamId': [2, 2],
            'correlationId': [1268, 1273],
            'db_id': [409726, 409726],
        }),
    }


def test_find_cann_pid():
    # 测试找到 CANN PID 的情况
    trace_events = [
        {"name": "process_name", "args": {"name": "CANN"}, "pid": 123},
        {"name": "other_event", "args": {}, "pid": 456}
    ]
    assert find_cann_pid(trace_events) == 123

    # 测试未找到 CANN PID 的情况
    trace_events = [
        {"name": "process_name", "args": {"name": "OTHER"}, "pid": 123},
        {"name": "other_event", "args": {}, "pid": 456}
    ]
    assert find_cann_pid(trace_events) is None


def test_load_single_prof_file_not_found():
    # 模拟 ms_open 在文件不存在时抛出 OpenException
    with patch("ms_service_profiler.exporters.exporter_trace.ms_open",
               side_effect=OpenException("No such file or directory")):
        result = load_single_prof("nonexistent_path.json", [])
        assert result == {"traceEvents": []}


def test_load_single_prof_invalid_json():
    mock_file = mock_open(read_data="invalid json").return_value
    mock_file.read.return_value = "invalid json"

    with patch("ms_service_profiler.exporters.exporter_trace.ms_open", return_value=mock_file) as mock_ms_open:
        result = load_single_prof("invalid_path.json", [])
        assert result == {"traceEvents": []}
        mock_ms_open.assert_called_once_with("invalid_path.json", mode="r")


def test_merge_json_data():
    # 测试合并 JSON 数据
    trace_data = {"traceEvents": [{"name": "event1", "pid": 123}]}
    msprof_data_df = [
        {"traceEvents": [{"name": "event2", "pid": 123}]},
        {"traceEvents": [{"name": "event3", "pid": 456}]}
    ]
    result = merge_json_data(trace_data, msprof_data_df)
    assert result == {
        "traceEvents": [
            {"name": "event1", "pid": 123},
            {"name": "event2", "pid": 123},
            {"name": "event3", "pid": 456}
        ]
    }


def test_integration(mock_data):
    # 集成测试：模拟多个文件的加载和合并
    mock_json_content = json.dumps([
        {"name": "process_name", "args": {"name": "CANN"}, "pid": 123},
        {"name": "event1", "pid": 123, "tid": 123},
        {"name": "event2", "pid": 456}
    ])

    # 模拟 ms_open 的行为，使其返回预设的 JSON 内容
    mock_file = mock_open(read_data=mock_json_content).return_value
    mock_file.read.return_value = mock_json_content

    with patch("ms_service_profiler.exporters.exporter_trace.ms_open", return_value=mock_file) as mock_ms_open:
        trace_data = {"traceEvents": []}
        for pf in mock_data["msprof_data"]:
            result = load_single_prof(pf, ["123"])
            trace_data = merge_json_data(trace_data, [result])

        # 验证 ms_open 被正确调用
        mock_ms_open.assert_called()
        assert len(trace_data["traceEvents"]) == 9


# 测试 ExporterTrace 初始化
def test_exporter_initialize():
    mock_args = mock.Mock()
    ExporterTrace.initialize(mock_args)
    assert ExporterTrace.args == mock_args


# 测试 ExporterTrace 的 export 方法
@mock.patch('ms_service_profiler.exporters.exporter_trace.create_trace_events')
@mock.patch('ms_service_profiler.exporters.exporter_trace.save_trace_data_into_json')
@mock.patch('ms_service_profiler.exporters.exporter_trace.ms_open')
def test_exporter_export(mock_ms_open, mock_save, mock_create, mock_data, mock_mspti):
    # 模拟 ms_open 的行为，使其返回预设的文件内容
    mock_file = mock_open(read_data='{"traceEvents": []}').return_value
    mock_file.read.return_value = '{"traceEvents": []}'
    mock_ms_open.return_value = mock_file

    # 模拟 create_trace_events 返回值
    mock_create.return_value = {'traceEvents': []}
    mock_save.return_value = None  # 模拟保存行为

    ExporterTrace.initialize(mock.Mock(output_path='/tmp', format=['json']))
    ExporterTrace.export(mock_data, mock_mspti)

    # 验证 ms_open 被正确调用
    mock_ms_open.assert_called_once_with(mock.ANY, mode='r')

    # 验证 create_trace_events 被调用一次
    mock_create.assert_called_once()

    # 获取调用参数
    called_args, called_kwargs = mock_create.call_args

    # 手动验证参数中的 DataFrame 内容
    pd.testing.assert_frame_equal(called_args[0], mock_data['tx_data_df'])
    pd.testing.assert_frame_equal(called_args[1], mock_data['cpu_data_df'])
    pd.testing.assert_frame_equal(called_args[2], mock_data['memory_data_df'])


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
        {'tid': 'KVCache', 'name': 'event1'},
        {'tid': 'BatchSchedule', 'name': 'event2'},
        {'tid': 'Api', 'name': 'event3'},
        {'tid': 'Kernel', 'name': 'event4'},
    ]
    sorted_trace_events = sort_trace_events_by_tid(trace_events)

    # 验证事件是否按正确顺序排序
    assert sorted_trace_events[0]['tid'] == 'KVCache'
    assert sorted_trace_events[1]['tid'] == 'BatchSchedule'
    assert sorted_trace_events[2]['tid'] == 'Api'
    assert sorted_trace_events[3]['tid'] == 'Kernel'


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

    assert not result  # 应该返回空列表


def test_add_mem_events_none_input():
    # 输入为 None
    result = add_mem_events(None)

    assert not result  # 应该返回空列表


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


def test_add_npu_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'usage=': [0.5, 0.75, 0.25],
    }
    df = pd.DataFrame(data)

    result = add_npu_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'NPU Usage'
    assert result[0]["ph"] == "C"
    assert result[0]['args'] == {'Usage': 0.5}
    assert result[1]['args'] == {'Usage': 0.75}
    assert result[2]['args'] == {'Usage': 0.25}


def test_add_npu_events_none_input():
    # 输入为 None
    result = add_npu_events(None)

    assert not result  # 应该返回空列表


def test_add_npu_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'usage='])  # 没有数据的 DataFrame

    result = add_npu_events(df)

    assert not result  # 应该返回空列表


def test_add_kvcache_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'deviceBlock=': [0, 1, 2],
        'domain': ['KVCache', 'KVCache', 'KVCache'],
        'pid': [1, 1, 1],
        "scope#dp": [0, 0, 0],
    }
    df = pd.DataFrame(data)

    result = add_kvcache_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'KVCache-dp0'
    assert result[0]['pid'] == 1
    assert result[0]["ph"] == "C"
    assert result[0]['args'] == {'Device Block': 0}
    assert result[1]['args'] == {'Device Block': 1}
    assert result[2]['args'] == {'Device Block': 2}


def test_add_cpu_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'usage': [0.5, 0.75, 0.25],
    }
    df = pd.DataFrame(data)

    result = add_cpu_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'CPU Usage'
    assert result[0]["ph"] == "C"
    assert result[0]['args'] == {'CPU Usage': 0.5}
    assert result[1]['args'] == {'CPU Usage': 0.75}
    assert result[2]['args'] == {'CPU Usage': 0.25}


def test_add_cpu_events_none_input():
    # 输入为 None
    result = add_cpu_events(None)

    assert not result  # 应该返回空列表


def test_add_cpu_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'usage'])  # 没有数据的 DataFrame

    result = add_cpu_events(df)

    assert not result  # 应该返回空列表


def test_add_pull_kvcache_events_valid_data():
    data = {
        'start_time': [1000, 2000, 3000],
        'end_time': [1500, 2500, 3500],
        'rank': [0, 1, 2],
        'domain': ['PullKVCache', 'PullKVCache', 'PullKVCache'],
        'during_time': [500, 500, 500],
    }

    df = pd.DataFrame(data)

    result = add_pull_kvcache_events(df)

    assert len(result) == 3
    assert result[0]['name'] == 'PullKVCache'
    assert result[0]['pid'] == 'PullKVCache'
    assert result[0]["ph"] == "X"
    assert result[0]['dur'] == 500
    assert result[0]['args'] == {'rank': 0, 'during_time': 500, 'end_time': 1500, 'start_time': 1000}


def test_add_pull_kvcache_events_none_input():
    # 输入为 None
    result = add_pull_kvcache_events(None)

    assert not result  # 应该返回空列表


def test_add_pull_kvcache_events_empty_df():
    # 空 DataFrame
    df = pd.DataFrame(columns=['start_time', 'end_time', 'rank', 'domain', 'during_time'])  # 没有数据的 DataFrame

    result = add_pull_kvcache_events(df)

    assert not result  # 应该返回空列表


class MockFile:
    def __init__(self, file_content=""):
        self.file_content = file_content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def read(self):
        return self.file_content

    def write(self, str):
        self.file_content += str


@mock.patch('ms_service_profiler.exporters.exporter_trace.ms_open')
@mock.patch('ms_service_profiler.exporters.exporter_trace.logger')
def test_save_trace_data_into_json(mock_logger, mock_ms_open):
    fake_file = MockFile()
    mock_ms_open.return_value = fake_file
    save_trace_data_into_json({'traceEvents': [{}]}, 'output')
    assert (fake_file.read() == '{"traceEvents":[{}]}')
    mock_logger.info.assert_called_once()


@mock.patch('ms_service_profiler.exporters.exporter_trace.ms_open')
@mock.patch('ms_service_profiler.exporters.exporter_trace.json.dumps')
@mock.patch('ms_service_profiler.exporters.exporter_trace.logger')
def test_save_trace_data_into_json_exception(mock_logger, mock_dumps, mock_ms_open):
    mock_dumps.side_effect = Exception('Test exception')
    fake_file = MockFile()
    mock_ms_open.return_value = fake_file
    save_trace_data_into_json({'traceEvents': [123]}, 'output')
    mock_dumps.assert_called_once()
    assert (fake_file.read() == '{"traceEvents":[]}')
    mock_logger.error.assert_called_once()
