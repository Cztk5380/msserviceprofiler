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

from unittest.mock import patch

import pytest
import pandas as pd

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus, ReqStatus, parse_message_state_name, \
    status_index_to_status_name, is_req_status_metric, is_metric


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
    assert '0+' not in sample_data


def test_parse_invalid_data(sample_data):
    sample_data_invalid = sample_data.copy()
    sample_data_invalid['tx_data_df'] = None

    plugin = PluginReqStatus()
    
    assert sample_data_invalid == plugin.parse(sample_data_invalid)


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


def test_status_index_to_status_name():
    assert status_index_to_status_name('0+') == 'WAITING+'
    assert status_index_to_status_name('1=') == 'PENDING='
    assert status_index_to_status_name('2') == '2'  # Invalid format (should return original string)


def test_status_index_to_status_name_invalid():
    metric = '999+'
    assert metric == status_index_to_status_name(metric)


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

