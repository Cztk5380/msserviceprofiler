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
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus, ReqStatus, parse_message_state_name, \
    status_index_to_status_name, is_req_status_metric, is_metric, increase_value_to_real_value, count_req_state


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


def test_parse_valid_data(sample_data):
    plugin = PluginReqStatus()
    result = plugin.parse(sample_data)
    assert 'req_status_df' in result
    assert not result['req_status_df'].isna().any().any()  # Ensure there are no NaN values after processing


def test_parse_invalid_data(sample_data):
    sample_data_invalid = sample_data.copy()
    sample_data_invalid['tx_data_df'] = None

    plugin = PluginReqStatus()
    
    with pytest.raises(ValueError, match="tx_data_df is None"):
        plugin.parse(sample_data_invalid)


def test_parse_message_state_name():
    message = {'0+': 1, '1+': 2, '2+': 3}
    result = parse_message_state_name(message)
    assert result == {'WAITING+': 1, 'PENDING+': 2, 'RUNNING+': 3}


def test_parse_message_state_name_invalid():
    message = ['invalid_message']
    
    with pytest.raises(ValueError, match="Message must be a dict, but got <class 'list'>"):
        parse_message_state_name(message)


def test_is_req_status_metric():
    assert is_req_status_metric('0+') is True
    assert is_req_status_metric('1=') is True
    assert is_req_status_metric('2') is False
    assert is_req_status_metric('abc') is False


def test_is_metric():
    assert is_metric('1+') is True
    assert is_metric('1=') is True
    assert is_metric('1') is False


def test_status_index_to_status_name():
    assert status_index_to_status_name('0+') == 'WAITING+'
    assert status_index_to_status_name('1=') == 'PENDING='
    assert status_index_to_status_name('2') == '2'  # Invalid format (should return original string)


def test_status_index_to_status_name_invalid():
    with pytest.raises(ValueError, match="Invalid status index: 999"):
        status_index_to_status_name('999+')
    

def test_count_req_state():
    # Prepare mock data
    inc_df = pd.DataFrame({
        'name': ['httpReq', 'ReqState'],
        '0+': [1, None],
        '1+': [None, 2],
        '2+': [None, 3],
    })
    df = inc_df.copy()
    cur = [0, 0, 0]
    
    # Call the function
    count_req_state(inc_df, df, cur, 1, 2)
    
    # Check if the correct values have been updated
    assert pd.isna(df.iloc[1, 1])


@pytest.mark.parametrize("metric, expected", [
    ('0+', True),
    ('1=', True),
    ('2', False),
    ('abc', False),
])
def test_is_req_status_metric_parametric(metric, expected):
    assert is_req_status_metric(metric) == expected


@pytest.mark.parametrize("message, expected", [
    ({'0+': 1, '1+': 2, '2+': 3}, {'WAITING+': 1, 'PENDING+': 2, 'RUNNING+': 3}),
    ({'1+': 1}, {'PENDING+': 1}),
])
def test_parse_message_state_name_parametric(message, expected):
    assert parse_message_state_name(message) == expected


def test_plugin_req_status_with_valid_data(sample_data):
    plugin = PluginReqStatus()
    result = plugin.parse(sample_data)
    
    assert 'req_status_df' in result
    assert isinstance(result['req_status_df'], pd.DataFrame)
    assert not result['req_status_df'].isna().any().any()  # Ensure no NaN values in req_status_df
