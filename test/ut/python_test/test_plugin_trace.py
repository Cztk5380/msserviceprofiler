# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from unittest.mock import patch

import pytest
import pandas as pd

from ms_service_profiler.plugins.plugin_trace import PluginTrace, extract_batch_type, extract_batch_size, \
    extract_batch_size_when_pd_mixed


@pytest.fixture
def pd_mixed_sample_data():
    data = {
        'tx_data_df': pd.DataFrame({
            'name': ['ModelExec'],
            'start_time': [1696321692],
            'token_id_list': [[0, 1, 2, 3]],
            'rid_list': [[1, 1, 1, 1]],
        })
    }
    return data


@pytest.fixture
def sample_data():
    data = {
        'tx_data_df': pd.DataFrame({
            'name': ['ModelExec'],
            'start_time': [1696321692],
            'token_id_list': [[1, 2, 3, 4]],
            'rid_list': [[1, 1, 1, 1]],
        })
    }
    return data


def test_extract_batch_type_when_all_prefill():
    token_id_list = [0, 0, 0, 0]
    batch_type = None

    result = extract_batch_type(token_id_list, batch_type)
    assert result == 'Prefill'


def test_extract_batch_type_when_all_decode():
    token_id_list = [1, 2, 3, 4]
    batch_type = None

    result = extract_batch_type(token_id_list, batch_type)
    assert result == 'Decode'


def test_extract_batch_type_when_valid():
    token_id_list = [0, 1, 2, 3]
    batch_type = None

    result = extract_batch_type(token_id_list, batch_type)
    assert result == 'Prefill, Decode'


def test_extract_batch_type_when_none():
    token_id_list = None
    batch_type = None

    result = extract_batch_type(token_id_list, batch_type)
    assert result is None


def test_extract_batch_size_when_valid():
    rid_list = [0, 1, 2, 3]

    result = extract_batch_size(rid_list)
    assert result == '4'


def test_extract_batch_size_when_none():
    rid_list = None

    result = extract_batch_size(rid_list)
    assert result is None


def test_extract_batch_size_when_pd_mixed_valid():
    token_id_list = [0, 1, 2, 3]

    prefill_batch_size, decode_batch_size = extract_batch_size_when_pd_mixed(token_id_list)
    assert prefill_batch_size == 1
    assert decode_batch_size == 3


def test_parse_when_none():
    data = {}

    plugin = PluginTrace()
    with pytest.raises(ValueError, match="tx_data_df is None"):
        plugin.parse(data)


def test_parse_when_pd_mixed(pd_mixed_sample_data):
    plugin = PluginTrace()
    data = plugin.parse(pd_mixed_sample_data)
    result = data['tx_data_df']
    assert result['batch_type'][0] == 'Prefill, Decode'
    assert result['batch_size'][0] == '4'
    assert result['prefill_batch_size'][0] == 1
    assert result['decode_batch_size'][0] == 3


def test_parse_when_valid(sample_data):
    plugin = PluginTrace()
    data = plugin.parse(sample_data)
    result = data['tx_data_df']
    assert result['batch_type'][0] == 'Decode'
    assert result['batch_size'][0] == '4'
    assert result['prefill_batch_size'][0] is None
    assert result['decode_batch_size'][0] is None
