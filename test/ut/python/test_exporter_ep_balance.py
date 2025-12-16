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
Args = type('Args', (object,), {'output_path': test_path, 'format': ['csv', "json"]})


def test_exporter_ep_balance():
    try:
        os.makedirs(test_path, exist_ok=True)
        os.chmod(test_path, 0o740)
        # 设置日志记录
        file_csv_path = Path(test_path, 'ep_balance.csv')
        file_png_path = Path(test_path, 'ep_balance.png')
        # 初始化args
        ExporterEpBalance.initialize(Args)
        # 调用export方法
        ExporterEpBalance.export(data)
        # 验证CSV文件是否生成
        assert file_csv_path.is_file()
        assert file_png_path.is_file()
    finally:
        # 清理
        shutil.rmtree(test_path)
