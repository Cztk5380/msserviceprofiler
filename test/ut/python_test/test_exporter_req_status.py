# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import os
import sqlite3
from pathlib import Path
import shutil
import pytest
import pandas as pd
from ms_service_profiler.exporters.exporter_req_status import ExporterReqStatus
from ms_service_profiler.exporters.utils import create_sqlite_db, visual_db_fp


@pytest.fixture
def sample_data():
    data = {
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
            'PULLED': [0, 0, 1]
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
        ExporterReqStatus.initialize({'parse_type': ['db']})
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

    
