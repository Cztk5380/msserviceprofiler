
# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from unittest.mock import patch

import pytest
import pandas as pd

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.plugins.plugin_metric import PluginMetric, is_metric


@pytest.fixture
def sample_data():
    data = {
        'tx_data_df': pd.DataFrame({
            'name': ['httpReq', 'ReqState', 'httpReq', 'ReqState'],
            'start_time': [1696321692, 1696321693, 1696321694, 169632165],
            'message': [{'0': 1}, {'1': 1}, {'0': 2}, {'2': 3}],
            '0+': [1, None, 2, None],
            '1+': [None, 1, None, 2],
            '2+': [None, None, None, 3],
        })
    }
    return data


def test_count(sample_data):
    plugin = PluginMetric()
    result = plugin.parse(sample_data)
    assert 'metric_data_df' in result
    assert all(result['metric_data_df']["0"] == [1, 1, 3, 3])


def test_is_metric():
    assert is_metric('1+') is True
    assert is_metric('1=') is True
    assert is_metric('1') is False