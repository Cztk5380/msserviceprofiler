# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import os
import shutil
from pathlib import Path
import pytest
import pandas as pd

from ms_service_profiler.exporters.exporter_ep_balance import ExporterEpBalance


data_per_pid = [100] * 58
data_ep_balance = {
    0: data_per_pid,
    1: data_per_pid,
    2: data_per_pid,
    3: data_per_pid
}
data = {"ep_balance": pd.DataFrame.from_dict(data_ep_balance)}
test_path = os.path.join(os.getcwd(), "ep_balance_output_test")
Args = type('Args', (object,), {'output_path': test_path, 'format': ['csv', "db", "json"]})


def test_exporter_ep_balance():
    try:
        os.makedirs(test_path, exist_ok=True)
        os.chmod(test_path, 0o740)
        # 设置日志记录
        file_csv_path = Path(test_path, 'ep_balance.csv')
        file_png_path = Path(test_path, 'ep_balance.png')
        file_db_path = Path(test_path, 'profiler.db')
        # 初始化args
        ExporterEpBalance.initialize(Args)
        # 调用export方法
        ExporterEpBalance.export(data)
        # 验证CSV文件是否生成
        assert file_csv_path.is_file()
        assert file_png_path.is_file()
        assert file_db_path.is_file()
    finally:
        # 清理
        shutil.rmtree(test_path)
