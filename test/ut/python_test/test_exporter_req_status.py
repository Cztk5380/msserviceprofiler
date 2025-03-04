# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import os
import sqlite3

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
            'RUNNING': [0, 1, 0],
            'END': [0, 0, 1],
        })
    }
    return data


def test_parse_valid_data(tmpdir, sample_data):
    """测试export"""
    ExporterReqStatus.initialize({})
    ExporterReqStatus.export(sample_data)

    db_fp = 'profiler.db'
    assert os.path.exists(db_fp)
    conn = sqlite3.connect(db_fp)
    res = pd.read_sql("SELECT * FROM request_status", conn)
    conn.close()
    assert sample_data["metric_data_df"].shape == res.shape
    assert sample_data["metric_data_df"].rename(
        columns={"start_datetime": "timestamp"}).equals(res)
