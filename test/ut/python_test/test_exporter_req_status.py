# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from unittest import mock

import os
import sqlite3
from pathlib import Path
import shutil
import pytest
import pandas as pd
import numpy as np
from ms_service_profiler.exporters.exporter_req_status import ExporterReqStatus
from ms_service_profiler.exporters.utils import create_sqlite_db, visual_db_fp


@pytest.fixture
def sample_data():
    data = {
        'tx_data_df': pd.DataFrame({
            'name': ['ReqState'],
            'domain': ['Request']}),
        'metric_data_df': pd.DataFrame({
            'start_datetime': [1696321692, 1696321693, 1696321694],
            'WAITING': [1, 0, 0],
            'PENDING': [1, 0, 0],
            'RUNNING': [0, 1, 0],
            'RUNNING2': [0, 1, 0],
            'SWAPPED': [0, 0, 1],
            'RECOMPUTE': [0, 0, 1],
            'SUSPENDED': [0, 0, 1],
            'END': [0, 0, 1],
            'STOP': [0, 0, 1],
            'PREFILL_HOLD': [0, 0, 1],
            'END_PRE': [0, 0, 1],
            'STOP_PRE': [0, 0, 1],
            'WAITING_PULL': [0, 0, 1],
            'PULLING': [0, 0, 1],
            'PULLED': [0, 0, 1],
            'D2D_PULLING': [0, 0, 1]
        })
    }
    return data


def test_parse_valid_data(tmpdir, sample_data):
    """测试export"""
    try:
        test_path = os.path.join(os.getcwd(), "output_test")
        os.makedirs(test_path, exist_ok=True)
        os.chmod(test_path, 0o740)
        create_sqlite_db(test_path)
        db_fp = Path(test_path, 'profiler.db')
        conn = sqlite3.connect(db_fp)
        ExporterReqStatus.initialize(mock.Mock(format=['json', 'csv', 'db']))
        ExporterReqStatus.export(sample_data)
        conn.close()
        assert os.path.exists(db_fp)
        conn = sqlite3.connect(db_fp)
        res = pd.read_sql("SELECT * FROM request_status", conn)
        conn.close()
        assert sample_data["metric_data_df"].shape == res.shape
        assert sample_data["metric_data_df"].rename(
            columns={"start_datetime": "timestamp"}).equals(res)
    finally:
        # 清理
        shutil.rmtree(test_path)


def test_export_with_csv_format():
    # 创建测试数据
    data = {
        'tx_data_df': pd.DataFrame({
            'hostuid': [1, 2, 3],
            'pid': [101, 101, 102],
            'start_time': [1000, 1010, 1020],
            'domain': ['Schedule', 'Schedule', 'Schedule'],
            'name': ['Queue', 'Queue', 'Queue'],
            'status': ['waiting', 'running', 'swapped'],
            'QueueSize=': [10, 15, 20],
        })
    }

    # 初始化 ExporterReqStatus
    args = type('Args', (object,), {'format': ['csv'], 'output_path': 'output_path'})()
    ExporterReqStatus.initialize(args)

    # 调用 export 方法
    with mock.patch('ms_service_profiler.exporters.exporter_req_status.save_dataframe_to_csv') \
        as mock_save_dataframe_to_csv:
        ExporterReqStatus.export(data)

        # 验证 save_dataframe_to_csv 被正确调用
        expected_df = pd.DataFrame({
            'hostuid': [1, 2, 3],
            'pid': [101, 101, 102],
            'timestamp(ms)': [1.0, 1.01, 1.02],
            'relative_timestamp(ms)': [0, 0.01, 0],
            'waiting': np.array([10, None, None]),
            'running': np.array([None, 15, None]),
            'swapped': np.array([None, None, 20])
        })
        print(mock_save_dataframe_to_csv.call_args[0][0]['relative_timestamp(ms)'])
        pd.testing.assert_frame_equal(mock_save_dataframe_to_csv.call_args[0][0], expected_df)
        assert mock_save_dataframe_to_csv.call_args[0][1] == 'output_path'
        assert mock_save_dataframe_to_csv.call_args[0][2] == 'request_status.csv'

def test_map_and_encode_status():
    # 准备测试数据
    data = {
        'status': ['waiting', 'running', 'waiting'],
        'other_column': [1, 2, 3]
    }
    df = pd.DataFrame(data)
    metrics = {'start_datetime': '2023-10-01 12:00:00'}

    # 调用方法
    result_df = ExporterReqStatus._map_and_encode_status(df, metrics)

    # 预期结果
    expected_data = {
        'timestamp': ['2023-10-01 12:00:00', '2023-10-01 12:00:00', '2023-10-01 12:00:00'],
        'WAITING': [True, False, True],
        'RUNNING': [False, True, False],
        'PENDING': [0, 0, 0]
    }

    expected_df = pd.DataFrame(expected_data)  # 显式指定数据类型为 int

    # 比较结果
    pd.testing.assert_frame_equal(result_df, expected_df)