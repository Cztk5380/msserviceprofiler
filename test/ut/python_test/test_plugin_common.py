# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import pytest
import pandas as pd
import numpy as np
from ms_service_profiler.plugins import PluginCommon
from ms_service_profiler.plugins.plugin_common import extract_ids_from_reslist, extract_rid, parse_rid_map
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import ParseError, DataFrameMissingError, KeyMissingError, ValidationError

# 示例数据
data = {
    "tx_data_df": pd.DataFrame({
        "rid": [1, 2, 3],
        "type": [3, 3, 3]
    }),
    "rid_link_map": {}
}


def test_parse_with_valid_data():
    tx_data_df = pd.DataFrame({
        "rid": [1, 2, 3],
        "type": [3, 3, 3]
    })
    rid_link_map = {}
    result = PluginCommon.parse({"tx_data_df": tx_data_df})
    assert "tx_data_df" in result
    assert "rid_link_map" in result
    assert len(result["tx_data_df"]) == 3
    assert len(result["rid_link_map"]) == 0


def test_parse_with_rid_none():
    tx_data_df = pd.DataFrame({
        "rid": None,
        "type": [3, 3, 3]
    })
    rid_link_map = {}
    result = PluginCommon.parse({"tx_data_df": tx_data_df})
    assert "tx_data_df" in result
    assert "rid_link_map" in result
    assert len(result["tx_data_df"]) == 3
    assert len(result["rid_link_map"]) == 0


def test_parse_with_missing_df():
    with pytest.raises(DataFrameMissingError):
        PluginCommon.parse({})


def test_parse_with_missing_columns():
    tx_data_df = pd.DataFrame({
        "rid": [1, 2, 3]
    })
    PluginCommon.parse({"tx_data_df": tx_data_df})
    assert 'rid_list' not in tx_data_df.columns


def test_parse_with_invalid_rid():
    tx_data_df = pd.DataFrame({
        "rid": [1, 2, 'a'],
        "type": [3, 3, 3]
    })
    result = PluginCommon.parse({"tx_data_df": tx_data_df})
    assert result["tx_data_df"].iloc[2]["rid"] == 'a'
    assert result["tx_data_df"].iloc[2]["rid_list"] is None
    assert result["tx_data_df"].iloc[2]["token_id_list"] is None


def test_parse_with_empty_rid_from_message():
    rid_from_message = []
    rid_map = {1: 1, 2: 2}
    rid, token_id, dp_id = extract_ids_from_reslist(rid_from_message, rid_map)
    assert len(rid) == 0
    assert len(token_id) == 0
    assert len(dp_id) == 0


def test_parse_with_string_rid_from_message():
    rid_from_message = ['a', 'b']
    rid_map = {1: 1, 2: 2}
    rid, token_id, dp_id = extract_ids_from_reslist(rid_from_message, rid_map)
    assert rid == ['a', 'b']
    assert len(rid) == 2
    assert len(token_id) == 2
    assert len(dp_id) == 0


def test_parse_with_list_rid_from_message():
    rid_from_message = [{'rid': 1}, {'rid': 2}]
    rid_map = {1: 1, 2: 2}
    rid, token_id, dp_id = extract_ids_from_reslist(rid_from_message, rid_map)
    assert rid == ['1', '2']
    assert token_id == [None, None]
    assert not dp_id


def test_parse_with_invalid_rid_from_message():
    rid_from_message = [{'rid': 'a'}, {'rid': 'b'}]
    rid_map = {1: 1, 2: 2}
    rid, token_id, dp_id = extract_ids_from_reslist(rid_from_message, rid_map)
    assert rid == ['a', 'b']
    assert token_id == [None, None]
    assert not dp_id


def test_parse_with_invalid_rid_link_map():
    df = pd.DataFrame({
        "type": [3, 3],
        "to": [1, 2],
        "from": ['a', 'b']
    })
    rid_link_map = parse_rid_map(df)
    assert isinstance(rid_link_map, dict)
    assert len(rid_link_map) == 2
    assert rid_link_map == {1: 'a', 2: 'b'}


def test_extract_ids_from_reslist():
    rid_from_message = [{'rid': 1}, {'rid': 2}]
    rid_map = {1: 1, 2: 2}
    rid, token_id, dp_id = extract_ids_from_reslist(rid_from_message, rid_map)
    assert rid == ['1', '2']
    assert token_id == [None, None]
    assert not dp_id


def test_extract_rid_with_string_input():
    rid_from_message = '1'
    rid_map = {1: 1}
    rid, rid_list, token_id_list, dp_id = extract_rid(rid_from_message, rid_map)
    assert rid == '1'
    assert rid_list is None
    assert token_id_list is None
    assert dp_id is None


def test_extract_rid_with_list_input():
    rid_from_message = [1, 2]
    rid_map = {1: 1, 2: 2}
    rid, rid_list, token_id_list, dp_id = extract_rid(rid_from_message, rid_map)
    assert rid == '1,2'
    assert rid_list == [1, 2]
    assert token_id_list == [None, None]
    assert not dp_id


def test_extract_rid_with_invalid_input():
    rid_from_message = None
    rid_map = None
    rid, rid_list, token_id_list, dp_id = extract_rid(rid_from_message, rid_map)
    assert rid is None
    assert rid_list is None
    assert token_id_list is None
    assert dp_id is None


def test_extract_dp_from_reslist():
    rid_from_message = [{'rid': 1, 'dp': '0'}, {'rid': 2, 'dp': '1'}]
    rid_map = {1: 1, 2: 2}
    rid, token_id, dp_id = extract_ids_from_reslist(rid_from_message, rid_map)
    assert rid == ['1', '2']
    assert not token_id
    assert dp_id == ['0', '1']
