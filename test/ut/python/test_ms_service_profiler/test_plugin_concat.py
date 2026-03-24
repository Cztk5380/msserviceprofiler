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
from collections import defaultdict

import pytest
import pandas as pd
from ms_service_profiler.plugins.plugin_concat import PluginConcat

@pytest.fixture
def sample_dataframes():
    df1 = pd.DataFrame({'start_time': [2, 1], 'data': [20, 10]})
    df2 = pd.DataFrame({'start_time': [4, 3], 'data': [40, 30]})
    return [{'merged_key': df1}, {'merged_key': df2}]


def test_merge_multiple_dataframes(sample_dataframes):
    result = PluginConcat.parse(sample_dataframes)
    merged_df = result['merged_key']

    assert len(merged_df) == 4
    pd.testing.assert_series_equal(
        merged_df['start_time'],
        pd.Series([1, 2, 3, 4], name='start_time')
    )


def test_msprof_merge_with_variants():
    df_list = [pd.DataFrame({'start_time': [1]}),
               pd.DataFrame({'start_time': [2]})]
    df_single = pd.DataFrame({'start_time': [3]})

    data = [
        {'msprof_data': df_list},
        {'msprof_data': df_single},
        {'msprof_data': None}  # 测试None值情况
    ]
    result = PluginConcat.parse(data)

    assert len(result['msprof_data']) == 3
    assert all(isinstance(df, pd.DataFrame) for df in result['msprof_data'])


def test_non_dataframe_values_ignored():
    data = [{'str_key': 'invalid_data'}, {'int_key': 123}]
    result = PluginConcat.parse(data)

    assert 'str_key' not in result
    assert 'int_key' not in result


def test_empty_data_input():
    result = PluginConcat.parse([])
    assert isinstance(result, defaultdict)
    assert len(result) == 0


def test_build_rid_hash_mapping_returns_empty_for_none_empty_or_missing_columns():
    assert PluginConcat._build_rid_hash_mapping(None) == {}
    assert PluginConcat._build_rid_hash_mapping(pd.DataFrame()) == {}
    assert PluginConcat._build_rid_hash_mapping(pd.DataFrame([{'start_time': 1, 'name': 'httpReq'}])) == {}
    assert PluginConcat._build_rid_hash_mapping(pd.DataFrame([{'start_time': 1, 'rid': 'req1'}])) == {}


def test_build_rid_hash_mapping_returns_empty_when_no_original_rid_source_exists():
    tx_data_df = pd.DataFrame([
        {'start_time': 1, 'name': 'QueueEnter', 'rid': 'req1-1234abcd'},
        {'start_time': 2, 'name': 'modelExec', 'rid': 'req1-1234abcd'}
    ])

    assert PluginConcat._build_rid_hash_mapping(tx_data_df) == {}


def test_dataframe_sorting_reset_index():
    unsorted_df = pd.DataFrame({
        'start_time': [30, 10, 20],
        'data': ['c', 'a', 'b']
    })
    data = [{'sorted_key': unsorted_df}]
    result = PluginConcat.parse(data)

    sorted_df = result['sorted_key']
    expected_order = [10, 20, 30]
    assert sorted_df['start_time'].tolist() == expected_order
    assert sorted_df.index.tolist() == [0, 1, 2]


def test_hash_rid_mapping_updates_all_rid_shapes():
    tx_data_df = pd.DataFrame([
        {'start_time': 1, 'name': 'httpReq', 'rid': 'req1'},
        {'start_time': 2, 'name': 'tokenize', 'rid': 'req2'},
        {
            'start_time': 3,
            'name': 'modelExec',
            'rid': 'req1-1234abcd',
            'rid_list': ['req1-1234abcd'],
            'res_list': [{'rid': 'req1-1234abcd', 'iter': 0}]
        },
        {
            'start_time': 4,
            'name': 'specDecoding',
            'rid': 'req1-1234abcd,req2-5678dcba',
            'rid_list': ['req1-1234abcd', 'req2-5678dcba'],
            'res_list': [{'rid': 'req1-1234abcd', 'iter': 0}, {'rid': 'req2-5678dcba', 'iter': 1}]
        }
    ])

    result = PluginConcat.parse([{'tx_data_df': tx_data_df}])
    merged_df = result['tx_data_df']

    assert merged_df.loc[2, 'rid'] == 'req1'
    assert merged_df.loc[2, 'rid_list'] == ['req1']
    assert merged_df.loc[2, 'res_list'][0]['rid'] == 'req1'
    assert merged_df.loc[3, 'rid'] == 'req1,req2'
    assert merged_df.loc[3, 'rid_list'] == ['req1', 'req2']
    assert [item['rid'] for item in merged_df.loc[3, 'res_list']] == ['req1', 'req2']


def test_build_rid_hash_mapping_reads_joined_rid_and_res_list():
    tx_data_df = pd.DataFrame([
        {'start_time': 1, 'name': 'httpReq', 'rid': 'alpha'},
        {'start_time': 2, 'name': 'httpReq', 'rid': 'beta'},
        {
            'start_time': 3,
            'name': 'specDecoding',
            'rid': 'alpha-aaaaaaaa,beta-bbbbbbbb',
            'rid_list': ['alpha-aaaaaaaa', 'beta-bbbbbbbb'],
            'res_list': [{'rid': 'alpha-aaaaaaaa'}, {'rid': 'beta-bbbbbbbb'}]
        }
    ])

    rid_map = PluginConcat._build_rid_hash_mapping(tx_data_df)

    assert rid_map == {
        'alpha-aaaaaaaa': 'alpha',
        'beta-bbbbbbbb': 'beta'
    }


def test_build_rid_hash_mapping_supports_multiple_variants_for_one_original_rid():
    tx_data_df = pd.DataFrame([
        {'start_time': 1, 'name': 'httpReq', 'rid': 'root-rid'},
        {'start_time': 2, 'name': 'QueueEnter', 'rid': 'root-rid-A'},
        {
            'start_time': 3,
            'name': 'specDecoding',
            'rid': 'root-rid-A,root-rid-B',
            'rid_list': ['root-rid-A', 'root-rid-B'],
            'res_list': [{'rid': 'root-rid-A'}, {'rid': 'root-rid-B'}]
        }
    ])

    rid_map = PluginConcat._build_rid_hash_mapping(tx_data_df)
    result = PluginConcat.parse([{'tx_data_df': tx_data_df}])['tx_data_df']

    assert rid_map == {
        'root-rid-A': 'root-rid',
        'root-rid-B': 'root-rid'
    }
    assert result.loc[1, 'rid'] == 'root-rid'
    assert result.loc[2, 'rid'] == 'root-rid,root-rid'
    assert result.loc[2, 'rid_list'] == ['root-rid', 'root-rid']
    assert [item['rid'] for item in result.loc[2, 'res_list']] == ['root-rid', 'root-rid']


def test_hash_rid_mapping_with_only_httpreq_and_tokenize_as_original_sources():
    tx_data_df = pd.DataFrame([
        {'start_time': 1, 'name': 'httpReq', 'rid': 'req-basic', 'domain': 'Request'},
        {'start_time': 2, 'name': 'tokenize', 'rid': 'req-basic', 'domain': 'Request'},
        {'start_time': 3, 'name': 'QueueEnter', 'rid': 'req-basic-1234abcd', 'domain': 'Schedule'},
        {
            'start_time': 4,
            'name': 'BatchSchedule',
            'rid': 'req-basic-1234abcd,req-basic-5678dcba',
            'rid_list': ['req-basic-1234abcd', 'req-basic-5678dcba'],
            'res_list': [{'rid': 'req-basic-1234abcd', 'iter': 0}, {'rid': 'req-basic-5678dcba', 'iter': 1}],
            'domain': 'Schedule'
        },
        {
            'start_time': 5,
            'name': 'modelExec',
            'rid': 'req-basic-1234abcd',
            'rid_list': ['req-basic-1234abcd'],
            'res_list': [{'rid': 'req-basic-1234abcd', 'iter': 0}],
            'domain': 'Execute'
        },
        {'start_time': 6, 'name': 'httpRes', 'rid': 'req-basic-1234abcd', 'domain': 'Request'}
    ])

    rid_map = PluginConcat._build_rid_hash_mapping(tx_data_df)
    result = PluginConcat.parse([{'tx_data_df': tx_data_df}])['tx_data_df']

    assert rid_map == {
        'req-basic-1234abcd': 'req-basic',
        'req-basic-5678dcba': 'req-basic'
    }
    assert result.loc[0, 'rid'] == 'req-basic'
    assert result.loc[1, 'rid'] == 'req-basic'
    assert result.loc[2, 'rid'] == 'req-basic'
    assert result.loc[3, 'rid'] == 'req-basic,req-basic'
    assert result.loc[3, 'rid_list'] == ['req-basic', 'req-basic']
    assert [item['rid'] for item in result.loc[3, 'res_list']] == ['req-basic', 'req-basic']
    assert result.loc[4, 'rid'] == 'req-basic'
    assert result.loc[5, 'rid'] == 'req-basic'


def test_hash_rid_mapping_supports_multiple_hashed_branches_for_same_original_rid():
    tx_data_df = pd.DataFrame([
        {'start_time': 1, 'name': 'httpReq', 'rid': 'req-recompute', 'domain': 'Request'},
        {'start_time': 2, 'name': 'tokenize', 'rid': 'req-recompute', 'domain': 'Request'},
        {'start_time': 3, 'name': 'QueueEnter', 'rid': 'req-recompute-aaaabbbb', 'domain': 'Schedule'},
        {'start_time': 4, 'name': 'QueueEnter', 'rid': 'req-recompute-ccccdddd', 'domain': 'Schedule'},
        {
            'start_time': 5,
            'name': 'BatchSchedule',
            'rid': 'req-recompute-aaaabbbb,req-recompute-eeeeffff',
            'rid_list': ['req-recompute-aaaabbbb', 'req-recompute-eeeeffff'],
            'res_list': [{'rid': 'req-recompute-aaaabbbb', 'iter': 0}, {'rid': 'req-recompute-eeeeffff', 'iter': 1}],
            'domain': 'Schedule'
        },
        {
            'start_time': 6,
            'name': 'specDecoding',
            'rid': 'req-recompute-ccccdddd,req-recompute-eeeeffff',
            'rid_list': ['req-recompute-ccccdddd', 'req-recompute-eeeeffff'],
            'res_list': [{'rid': 'req-recompute-ccccdddd', 'iter': 2}, {'rid': 'req-recompute-eeeeffff', 'iter': 3}],
            'domain': 'Execute'
        }
    ])

    rid_map = PluginConcat._build_rid_hash_mapping(tx_data_df)
    result = PluginConcat.parse([{'tx_data_df': tx_data_df}])['tx_data_df']

    assert rid_map == {
        'req-recompute-aaaabbbb': 'req-recompute',
        'req-recompute-ccccdddd': 'req-recompute',
        'req-recompute-eeeeffff': 'req-recompute'
    }
    assert result.loc[2, 'rid'] == 'req-recompute'
    assert result.loc[3, 'rid'] == 'req-recompute'
    assert result.loc[4, 'rid'] == 'req-recompute,req-recompute'
    assert result.loc[4, 'rid_list'] == ['req-recompute', 'req-recompute']
    assert [item['rid'] for item in result.loc[4, 'res_list']] == ['req-recompute', 'req-recompute']
    assert result.loc[5, 'rid'] == 'req-recompute,req-recompute'
    assert result.loc[5, 'rid_list'] == ['req-recompute', 'req-recompute']
    assert [item['rid'] for item in result.loc[5, 'res_list']] == ['req-recompute', 'req-recompute']


def test_collect_rids_from_value_filters_empty_and_supports_nested_shapes():
    output_set = set()

    PluginConcat._collect_rids_from_value('', output_set)
    PluginConcat._collect_rids_from_value('  ', output_set)
    PluginConcat._collect_rids_from_value('nan', output_set)
    PluginConcat._collect_rids_from_value('None', output_set)
    PluginConcat._collect_rids_from_value('req1, req2 ,, req3 ', output_set)
    PluginConcat._collect_rids_from_value({'rid': ['req4', {'rid': 'req5'}]}, output_set)
    PluginConcat._collect_rids_from_value(('req6', 7), output_set)

    assert output_set == {'req1', 'req2', 'req3', 'req4', 'req5', 'req6', '7'}


def test_collect_unique_rids_from_series_ignores_none_series():
    output_set = {'keep'}

    PluginConcat._collect_unique_rids_from_series(None, output_set)

    assert output_set == {'keep'}


def test_find_original_rid_for_variant_prefers_hash_suffix_and_longest_prefix():
    original_rids = {'req', 'req-child', 'req-child-inner'}

    assert PluginConcat._find_original_rid_for_variant('req-child-1234abcd', original_rids) == 'req-child'
    assert PluginConcat._find_original_rid_for_variant('req-child-inner-A', original_rids) == 'req-child-inner'
    assert PluginConcat._find_original_rid_for_variant('req-child-inner-ffffeeee', original_rids) == 'req-child-inner'
    assert PluginConcat._find_original_rid_for_variant('unknown-1234abcd', original_rids) is None


def test_extract_all_rid_strs_supports_none_string_dict_list_and_scalar():
    assert list(PluginConcat._extract_all_rid_strs(None)) == []
    assert list(PluginConcat._extract_all_rid_strs('req1, req2')) == ['req1', 'req2']
    assert list(PluginConcat._extract_all_rid_strs({'rid': ['req3', {'rid': 'req4'}]})) == ['req3', 'req4']
    assert list(PluginConcat._extract_all_rid_strs(['req5', ('req6',)])) == ['req5', 'req6']
    assert list(PluginConcat._extract_all_rid_strs(123)) == ['123']


def test_map_rid_value_handles_tuple_dict_without_rid_and_blank_string():
    rid_map = {'req1-1234abcd': 'req1', 'req2-5678dcba': 'req2'}

    assert PluginConcat._map_rid_value('   ', rid_map) == '   '
    assert PluginConcat._map_rid_value(' , , ', rid_map) == ' , , '
    assert PluginConcat._map_rid_value(None, rid_map) is None
    assert PluginConcat._map_rid_value(('req1-1234abcd', 'req2-5678dcba'), rid_map) == ('req1', 'req2')
    assert PluginConcat._map_rid_value({'other': 'value'}, rid_map) == {'other': 'value'}
    assert PluginConcat._map_rid_value({'rid': 'req1-1234abcd,req2-5678dcba'}, rid_map) == {'rid': 'req1,req2'}


def test_get_mapping_rid_and_mapping_rid_cover_numeric_list_and_dict_paths():
    rid_map = {'1': 'req1', 'raw': 'mapped-raw'}

    assert PluginConcat._get_mapping_rid(1.0, rid_map) == 'req1'
    assert PluginConcat._get_mapping_rid('raw', None) == 'raw'
    assert PluginConcat._mapping_rid(['raw', 1.0], rid_map) == ['mapped-raw', 'req1']
    assert PluginConcat._mapping_rid({'rid': 1.0, 'iter': 0}, rid_map) == {'rid': 'req1', 'iter': 0}
    assert PluginConcat._mapping_rid('raw', rid_map) == 'mapped-raw'


def test_extract_rid_covers_list_dict_scalar_and_invalid_iter():
    rid, rid_list, token_id_list, dp_list = PluginConcat._extract_rid([
        {'rid': 'req1', 'iter': '2'},
        {'rid': 'req2', 'iter': 'bad'},
        {'rid': 'req3', 'dp': 'dp0'},
        'req4'
    ])

    assert rid == 'req1,req2,req3,req4'
    assert rid_list == ['req1', 'req2', 'req3', 'req4']
    assert token_id_list == [2, None, None]
    assert dp_list == ['dp0']

    scalar_rid, scalar_list, scalar_token_ids, scalar_dp_list = PluginConcat._extract_rid('single')
    assert scalar_rid == 'single'
    assert scalar_list == ['single']
    assert scalar_token_ids == []
    assert scalar_dp_list == []


def test_apply_rid_mapping_returns_original_dataframe_when_map_is_empty_or_rid_missing():
    df_without_rid = pd.DataFrame([{'start_time': 1, 'name': 'httpReq'}])
    df_with_rid = pd.DataFrame([{'start_time': 1, 'name': 'httpReq', 'rid': 'req1'}])

    assert PluginConcat._apply_rid_mapping(None, {'req1-1234abcd': 'req1'}) is None
    assert PluginConcat._apply_rid_mapping(df_without_rid, {'req1-1234abcd': 'req1'}) is df_without_rid
    assert PluginConcat._apply_rid_mapping(df_with_rid, {}) is df_with_rid


def test_apply_rid_mapping_updates_nested_columns_and_keeps_non_rid_dicts():
    data_df = pd.DataFrame([
        {
            'start_time': 1,
            'name': 'modelExec',
            'rid': 'req1-1234abcd,req2-5678dcba',
            'rid_list': ('req1-1234abcd', 'req2-5678dcba'),
            'res_list': [{'rid': 'req1-1234abcd'}, {'meta': 'keep'}]
        }
    ])
    rid_map = {'req1-1234abcd': 'req1', 'req2-5678dcba': 'req2'}

    result_df = PluginConcat._apply_rid_mapping(data_df.copy(), rid_map)

    assert result_df.loc[0, 'rid'] == 'req1,req2'
    assert result_df.loc[0, 'rid_list'] == ('req1', 'req2')
    assert result_df.loc[0, 'res_list'][0]['rid'] == 'req1'
    assert result_df.loc[0, 'res_list'][1] == {'meta': 'keep'}


def test_apply_rid_mapping_uses_non_string_path_for_nested_values():
    data_df = pd.DataFrame([
        {
            'start_time': 1,
            'name': 'modelExec',
            'rid': ['req1-1234abcd', 'req2-5678dcba'],
            'rid_list': ['req1-1234abcd', 'req2-5678dcba'],
            'res_list': ('req1-1234abcd', 'req2-5678dcba')
        }
    ])
    rid_map = {'req1-1234abcd': 'req1', 'req2-5678dcba': 'req2'}

    result_df = PluginConcat._apply_rid_mapping(data_df.copy(), rid_map)

    assert result_df.loc[0, 'rid'] == ['req1', 'req2']
    assert result_df.loc[0, 'rid_list'] == ['req1', 'req2']
    assert result_df.loc[0, 'res_list'] == ('req1', 'req2')


def test_parse_merges_pid_label_map_and_skips_non_dict_pid_label_map():
    tx_data_df = pd.DataFrame([
        {'start_time': 2, 'name': 'QueueEnter', 'rid': 'req1-1234abcd'},
        {'start_time': 1, 'name': 'httpReq', 'rid': 'req1'}
    ])

    result = PluginConcat.parse([
        {'tx_data_df': tx_data_df.iloc[[0]].copy(), 'pid_label_map': {'100': {'dp_rank': 0}}},
        {'tx_data_df': tx_data_df.iloc[[1]].copy(), 'pid_label_map': ['invalid']}
    ])

    assert result['pid_label_map'] == {'100': {'dp_rank': 0}}
    assert result['tx_data_df']['rid'].tolist() == ['req1', 'req1']
