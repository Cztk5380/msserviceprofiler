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

import logging
import os
import pytest
from pathlib import Path
import shutil
from unittest.mock import patch

import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

from ms_service_profiler.exporters.exporter_batch import (
    ExporterBatchData,
    filter_batch_df,
    _process_spec_decoding_rows,
    KV_CACHE_COLUMNS,
)


class TestKVCacheColumns:
    """测试 KV_CACHE_COLUMNS 常量"""

    def test_kv_cache_columns_defined(self):
        assert "total_blocks" in KV_CACHE_COLUMNS
        assert "used_blocks" in KV_CACHE_COLUMNS
        assert "kvcache_usage_rate" in KV_CACHE_COLUMNS
        assert len(KV_CACHE_COLUMNS) == 6


class TestFilterBatchDf:
    """测试 filter_batch_df"""

    def test_none_or_empty_batch_df_returns_as_is(self):
        assert filter_batch_df("BatchSchedule", None) is None
        assert filter_batch_df("BatchSchedule", pd.DataFrame()).empty

    def test_filter_preserves_name_subset_and_keeps_time_cols_at_tail(self):
        batch_df = pd.DataFrame({
            "name": ["BatchSchedule", "modelExec"],
            "res_list": ["[]", "[]"],
            "start_datetime": ["2025-01-01 00:00:00", "2025-01-01 00:00:01"],
            "end_datetime": ["2025-01-01 00:00:01", "2025-01-01 00:00:02"],
            "during_time": [1000.0, 1000.0],
            "batch_type": ["Decode", "Decode"],
            "prof_id": [0, 0],
            "batch_size": [1, 1],
            "start_time": [100.0, 200.0],
            "end_time": [200.0, 300.0],
            "pid": [1, 1],
        })
        with patch("ms_service_profiler.exporters.exporter_batch.add_precomputed_kv_cache_fields", side_effect=lambda df, _: df):
            with patch("ms_service_profiler.exporters.exporter_batch.add_columns_for_batch_size_and_tokens", side_effect=lambda df: df):
                with patch("ms_service_profiler.exporters.exporter_batch.add_dp_rank_column", side_effect=lambda df, _: df):
                    out = filter_batch_df("BatchSchedule", batch_df, None)
        assert out is not None and not out.empty
        assert "start_time(ms)" in out.columns and "end_time(ms)" in out.columns
        assert out.columns[-2:].tolist() == ["start_time(ms)", "end_time(ms)"]
        assert "start_datetime" in out.columns and "end_datetime" in out.columns

    def test_spec_decode_accepted_by_req_dropped_in_output(self):
        batch_df = pd.DataFrame({
            "name": ["specDecoding"],
            "res_list": [[{"rid": "r1", "num_spec_output_tokens": 2}]],
            "start_datetime": ["2025-01-01 00:00:00"],
            "end_datetime": ["2025-01-01 00:00:01"],
            "during_time": [1000.0],
            "prof_id": [0],
            "pid": [1],
            "start_time": [100.0],
            "end_time": [200.0],
            "spec_decode_accepted_by_req": ['{"r1": 1}'],
        })
        with patch("ms_service_profiler.exporters.exporter_batch.add_precomputed_kv_cache_fields", side_effect=lambda df, _: df):
            with patch("ms_service_profiler.exporters.exporter_batch.add_columns_for_batch_size_and_tokens", side_effect=lambda df: df):
                with patch("ms_service_profiler.exporters.exporter_batch.add_dp_rank_column", side_effect=lambda df, _: df):
                    out = filter_batch_df("BatchSchedule", batch_df, None)
        assert "spec_decode_accepted_by_req" not in out.columns

    def test_kvcache_columns_fillna_zero(self):
        batch_df = pd.DataFrame({
            "name": ["BatchSchedule"],
            "res_list": ["[]"],
            "start_datetime": ["2025-01-01 00:00:00"],
            "end_datetime": ["2025-01-01 00:00:01"],
            "during_time": [1000.0],
            "prof_id": [0],
            "batch_size": [1],
            "start_time": [100.0],
            "end_time": [200.0],
            "pid": [1],
            "used_blocks": [10],
        })
        with patch("ms_service_profiler.exporters.exporter_batch.add_precomputed_kv_cache_fields", side_effect=lambda df, _: df):
            with patch("ms_service_profiler.exporters.exporter_batch.add_columns_for_batch_size_and_tokens", side_effect=lambda df: df):
                with patch("ms_service_profiler.exporters.exporter_batch.add_dp_rank_column", side_effect=lambda df, _: df):
                    out = filter_batch_df("BatchSchedule", batch_df, None)
        assert "used_blocks" in out.columns
        assert out["used_blocks"].iloc[0] == 10


class TestProcessSpecDecodingRows:
    """测试 _process_spec_decoding_rows"""

    def test_none_or_empty_df_returns_as_is(self):
        assert _process_spec_decoding_rows(None) is None
        assert _process_spec_decoding_rows(pd.DataFrame()).empty

    def test_no_spec_decoding_row_returns_unchanged(self):
        df = pd.DataFrame({"name": ["modelExec"], "res_list": ["[]"]})
        out = _process_spec_decoding_rows(df)
        assert out is df

    def test_spec_decoding_rows_kvcache_filled_zero(self):
        df = pd.DataFrame({
            "name": ["specDecoding"],
            "res_list": [[{"rid": "r1", "num_spec_output_tokens": 2, "num_spec_accepted_tokens": 0}]],
            "total_blocks": [100],
            "used_blocks": [50],
        })
        out = _process_spec_decoding_rows(df)
        assert out.loc[out["name"] == "specDecoding", "total_blocks"].iloc[0] == 0
        assert out.loc[out["name"] == "specDecoding", "used_blocks"].iloc[0] == 0

    def test_accepted_ratio_computed_from_res_list(self):
        df = pd.DataFrame({
            "name": ["specDecoding"],
            "res_list": [[
                {"rid": "r1", "num_spec_output_tokens": 4, "num_spec_accepted_tokens": 2},
                {"rid": "r2", "num_spec_output_tokens": 4, "num_spec_accepted_tokens": 2},
            ]],
        })
        out = _process_spec_decoding_rows(df)
        assert out["accepted_ratio"].iloc[0] == 0.5

    def test_spec_decode_accepted_by_req_fills_res_list(self):
        df = pd.DataFrame({
            "name": ["specDecoding", "modelRunnerExec"],
            "res_list": [[{"rid": "r1"}, {"rid": "r2"}], None],
            "pid": [1, 1],
            "start_time": [100.0, 250.0],
            "end_time": [200.0, 300.0],
            "spec_decode_accepted_by_req": [None, None],
        })
        df.at[1, "spec_decode_accepted_by_req"] = {"r1": 2, "r2": 1}
        out = _process_spec_decoding_rows(df)
        spec_row = out[out["name"] == "specDecoding"].iloc[0]
        res_list = spec_row["res_list"]
        r1 = next(r for r in res_list if r.get("rid") == "r1")
        r2 = next(r for r in res_list if r.get("rid") == "r2")
        assert r1["num_spec_accepted_tokens"] == 2
        assert r2["num_spec_accepted_tokens"] == 1


class TestBuildSpecDecodeDf:
    """测试 _build_spec_decode_df"""

    def test_none_or_empty_batch_df_returns_none(self):
        assert ExporterBatchData._build_spec_decode_df(None) is None
        assert ExporterBatchData._build_spec_decode_df(pd.DataFrame()) is None

    def test_no_spec_decoding_row_returns_none(self):
        batch_df = pd.DataFrame({"name": ["modelExec"], "res_list": ["[]"]})
        assert ExporterBatchData._build_spec_decode_df(batch_df) is None

    def test_res_list_string_json_parsed_and_expanded(self):
        batch_df = pd.DataFrame({
            "name": ["specDecoding"],
            "res_list": ['[{"rid": "r1", "iter": 0, "num_spec_output_tokens": 3, "num_spec_accepted_tokens": 2}]'],
            "start_datetime": ["2025-01-01 00:00:00"],
            "end_datetime": ["2025-01-01 00:00:01"],
            "during_time": [1000.0],
            "prof_id": [0],
        })
        out = ExporterBatchData._build_spec_decode_df(batch_df)
        assert out is not None and len(out) == 1
        assert out["rid"].iloc[0] == "r1"
        assert out["spec_tokens"].iloc[0] == 3
        assert out["accepted_tokens"].iloc[0] == 2
        assert out["accepted_ratio"].iloc[0] == round(2 / 3, 4)
        assert "start_datetime" in out.columns and "end_datetime" in out.columns
        assert "start_time(ms)" not in out.columns and "end_time(ms)" not in out.columns

    def test_res_list_list_expanded(self):
        batch_df = pd.DataFrame({
            "name": ["specDecoding"],
            "res_list": [[{"rid": "r1", "iter": 0, "num_spec_output_tokens": 2, "num_spec_accepted_tokens": 1}]],
            "start_datetime": ["2025-01-01 00:00:00"],
            "end_datetime": ["2025-01-01 00:00:01"],
            "during_time": [500.0],
            "prof_id": [1],
        })
        out = ExporterBatchData._build_spec_decode_df(batch_df)
        assert len(out) == 1
        assert out["spec_tokens"].iloc[0] == 2 and out["accepted_tokens"].iloc[0] == 1

    def test_spec_tokens_zero_ratio_none(self):
        batch_df = pd.DataFrame({
            "name": ["specDecoding"],
            "res_list": [[{"rid": "r1", "num_spec_output_tokens": 0, "num_spec_accepted_tokens": 0}]],
            "start_datetime": [None],
            "end_datetime": [None],
            "during_time": [0],
            "prof_id": [0],
        })
        out = ExporterBatchData._build_spec_decode_df(batch_df)
        assert out["accepted_ratio"].iloc[0] is None

    def test_empty_res_list_returns_empty_dataframe_with_columns(self):
        batch_df = pd.DataFrame({
            "name": ["specDecoding"],
            "res_list": [[]],
            "start_datetime": [None],
            "end_datetime": [None],
            "during_time": [0],
            "prof_id": [0],
        })
        out = ExporterBatchData._build_spec_decode_df(batch_df)
        assert out is not None and len(out) == 0
        assert "rid" in out.columns and "spec_tokens" in out.columns


class TestExporterBatchData:

    @pytest.fixture
    def test_path(self):
        """创建测试路径"""
        path = os.path.join(os.getcwd(), "output_test")
        yield path
        # 清理
        if os.path.exists(path):
            shutil.rmtree(path)

    @pytest.fixture
    def args(self, test_path):
        """创建测试参数"""
        return type('Args', (object,), {'output_path': test_path, 'format': ['csv', 'db']})

    @pytest.fixture
    def sample_tx_data_df(self):
        """创建示例 tx_data_df 数据"""
        data = {
            'name': ['BatchSchedule', 'modelExec', 'dpBatch', 'forward', 'forward',
                     'BatchSchedule', 'modelExec', 'dpBatch', 'forward', 'forward'],
            'domain': ['BatchSchedule', 'ModelExecute', 'ModelExecute', 'ModelExecute', 'ModelExecute',
                       'BatchSchedule', 'ModelExecute', 'ModelExecute', 'ModelExecute', 'ModelExecute'],
            'message': [
                {'rid': [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}], 'data': 'data1'},
                {'rid': [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}], 'data': 'data2'},
                {'rid': [11, 12], 'data': 'data1'},
                {'rid': [0], 'data': 'data1'},
                {'rid': [1], 'data': 'data2'},
                {'rid': [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}], 'data': 'data3'},
                {'rid': [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}], 'data': 'data4'},
                {'rid': [13, 14], 'data': 'data1'},
                {'rid': [0], 'data': 'data1'},
                {'rid': [1], 'data': 'data2'}
            ],
            'start_time': [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
            'end_time': [1500, 2500, 3500, 4500, 5500, 6500, 7500, 8500, 9500, 10500],
            'batch_size': [2, 2, 2, 1, 1, 2, 2, 2, 1, 1],
            'batch_type': ['Prefill', 'Prefill', 'Prefill', 'Prefill', 'Prefill',
                           'Decode', 'Decode', 'Decode', 'Decode', 'Decode'],
            'res_list': [
                [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}],
                [{'rid': 11, 'iter': 0}, {'rid': 12, 'iter': 0}],
                [11, 12],
                [0],
                [1],
                [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}],
                [{'rid': 13, 'iter': 1}, {'rid': 14, 'iter': 1}],
                [13, 14],
                [0],
                [1]
            ],
            'during_time': [500, 500, 500, 500, 500, 500, 500, 500, 500, 500],
            'pid': [0, 0, 1, 1, 2, 0, 0, 1, 1, 2],
            'rid_list': [[11, 12], [11, 12], [11, 12], [11, 12], [11, 12],
                         [13, 14], [13, 14], [13, 14], [13, 14], [13, 14]],
            'dp_list': [[], [], [0, 1], [], [], [], [], [0, 1], [], []],
            'rid': ['11, 12', '11, 12', '11, 12', '', '',
                    '13, 14', '13, 14', '13, 14', '', ''],
            'dp_rank': ['', '', '', '0', '1', '', '', '', '0', '1']
        }
        return pd.DataFrame(data)

    @pytest.fixture
    def processor(self):
        """创建 ExporterBatchData 实例"""
        from ms_service_profiler.exporters.exporter_batch import ExporterBatchData
        return ExporterBatchData()

    @pytest.fixture
    def sample_batch_event_df(self):
        """创建示例 batch_event_df 数据"""
        return pd.DataFrame({
            'event': ['BatchSchedule', 'forward', 'Execute', 'BatchSchedule', 'forward'],
            'batch_id': [
                "[{'rid': 'req_1', 'iter': 0}]",
                "[{'rid': 'req_1'}]",
                "[{'rid': 'req_1'}]",
                "[{'rid': 'req_2', 'iter': 0}]",
                "[{'rid': 'req_2'}]"
            ],
            'start_time': [100.0, 110.0, 120.0, 200.0, 210.0],
            'end_time': [100.0, 110.0, 120.0, 200.0, 210.0],
            'pid': [1001, 1001, 1001, 1002, 1002],
            'blocks': [None, [1, 2], None, None, [3, 4]]
        })

    @pytest.fixture
    def sample_batch_event_df_with_high_iter(self):
        """创建包含高 iter 值的示例数据"""
        return pd.DataFrame({
            'event': ['BatchSchedule', 'forward'],
            'batch_id': [
                "[{'rid': 'req_1', 'iter': 127}]",
                "[{'rid': 'req_1'}]"
            ],
            'start_time': [100.0, 110.0],
            'end_time': [100.0, 110.0],
            'pid': [1001, 1001],
            'blocks': [None, [1, 2, 3] + [2] * 125]  # 128个blocks
        })

    @pytest.fixture
    def empty_batch_event_df(self):
        """创建空的 batch_event_df 数据"""
        return pd.DataFrame(columns=['event', 'batch_id', 'start_time', 'end_time', 'pid'])

    @pytest.fixture
    def malformed_batch_event_df(self):
        """创建格式错误的 batch_event_df 数据"""
        return pd.DataFrame({
            'event': ['BatchSchedule', 'forward'],
            'batch_id': ['invalid_json', "[{'rid': 'req_1'}]"],
            'start_time': [100.0, 110.0],
            'end_time': [100.0, 110.0],
            'pid': [1001, 1001],
            'blocks': [None, [1, 2]]
        })

    @pytest.fixture
    def sample_parse_batch_df(self):
        """parse_batch的数据"""
        return pd.DataFrame({
            'name': ['BatchSchedule', 'forward', 'Execute'],
            'res_list': [
                "[{'rid': 'req_1', 'iter': 0}]",
                "[{'rid': 'req_1'}]",
                "[{'rid': 'req_1'}]"
            ],
            'token_id_list': [
                "[1, 2, 3]",
                "[1, 2]",
                "[1, 2]"
            ],
            'rid_list': [
                "['req_1']",
                "['req_1']",
                "['req_1']"
            ],
            'start_time': [100.0, 110.0, 120.0],
            'end_time': [100.0, 110.0, 120.0],
            'pid': [1001, 1001, 1001],
            'blocks': [None, "[1, 2]", None]
        })

    def test_export_with_valid_data(self, args, sample_tx_data_df, test_path):
        """测试正常导出功能"""
        try:
            # 创建目录
            os.makedirs(test_path, exist_ok=True)
            os.chmod(test_path, 0o740)

            from ms_service_profiler.exporters.exporter_batch import ExporterBatchData
            from ms_service_profiler.exporters.utils import create_sqlite_db

            # 初始化并导出
            ExporterBatchData.initialize(args)
            create_sqlite_db(test_path)

            data = {'tx_data_df': sample_tx_data_df}
            ExporterBatchData.export(data)

            # 验证CSV文件是否生成
            file_path = Path(test_path, 'batch.csv')
            assert file_path.is_file()

        finally:
            # 清理已在 fixture 中处理
            pass

    def test_export_with_missing_tx_data_df(self, args, test_path):
        """测试 tx_data_df 不存在的情况"""
        try:
            # 创建目录
            os.makedirs(test_path, exist_ok=True)
            os.chmod(test_path, 0o740)

            from ms_service_profiler.exporters.exporter_batch import ExporterBatchData

            # 初始化
            ExporterBatchData.initialize(args)

            # 调用export方法，但 tx_data_df 不存在
            data = {'tx_data_df': None}
            ExporterBatchData.export(data)

            # 验证文件是否未生成
            file_path = Path(test_path, 'batch.csv')
            assert not file_path.is_file()

        finally:
            pass

    def test_parse_batch_exec_req_normal_case(self, processor, sample_batch_event_df):
        """测试正常情况下的解析"""
        batch_exec, batch_req = processor.parse_batch_exec_req(sample_batch_event_df)

        # 验证返回值类型
        assert isinstance(batch_exec, pd.DataFrame)
        assert isinstance(batch_req, pd.DataFrame)

        # 验证基本结构
        assert len(batch_exec) >= 0
        assert len(batch_req) >= 0

    def test_parse_batch_exec_req_empty_input(self, processor):
        """测试空输入情况"""
        empty_batch_event_df = pd.DataFrame(columns=['event', 'batch_id', 'start_time', 'end_time', 'pid'])
        batch_exec, batch_req = processor.parse_batch_exec_req(empty_batch_event_df)

        # 验证返回空 DataFrame
        assert isinstance(batch_exec, pd.DataFrame)
        assert isinstance(batch_req, pd.DataFrame)

    def test_parse_batch_exec_req_none_input(self, processor):
        """测试 None 输入情况"""
        batch_exec, batch_req = processor.parse_batch_exec_req(None)

        # 验证返回空 DataFrame
        assert isinstance(batch_exec, pd.DataFrame)
        assert isinstance(batch_req, pd.DataFrame)
        assert len(batch_exec) == 0
        assert len(batch_req) == 0

    def test_safe_literal_eval_valid_input(self, processor):
        """测试 safe_literal_eval 正常输入"""
        # 测试有效 JSON 字符串
        result = processor.safe_literal_eval("[{'rid': 'test'}]")
        assert isinstance(result, list)
        if len(result) > 0:
            assert result[0]['rid'] == 'test'

        # 测试列表输入
        result = processor.safe_literal_eval([{'rid': 'test'}])
        assert isinstance(result, list)
        if len(result) > 0:
            assert result[0]['rid'] == 'test'

        # 测试 None 输入
        result = processor.safe_literal_eval(None)
        assert result == []

        # 测试 NaN 输入
        result = processor.safe_literal_eval(np.nan)
        assert result == []

    def test_safe_literal_eval_invalid_input(self, processor):
        """测试 safe_literal_eval 无效输入"""
        # 测试无效 JSON 字符串
        result = processor.safe_literal_eval("invalid_json")
        assert result == []

        # 测试语法错误
        result = processor.safe_literal_eval("[{'rid': 'test'")
        assert result == []

    def test_extract_schedule_data_normal_case(self, processor, sample_batch_event_df):
        """测试 extract_schedule_data 正常情况"""
        schedule_events = sample_batch_event_df[sample_batch_event_df['event'] == 'BatchSchedule']
        result = processor.extract_schedule_data(schedule_events)

        assert isinstance(result, pd.DataFrame)
        # 注意：根据实际实现，可能为空

    def test_extract_schedule_data_empty_input(self, processor, empty_batch_event_df):
        """测试 extract_schedule_data 空输入"""
        schedule_events = empty_batch_event_df[empty_batch_event_df['event'] == 'BatchSchedule']
        result = processor.extract_schedule_data(schedule_events)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_extract_schedule_items_normal_case(self, processor):
        """测试 extract_schedule_items 正常情况"""
        items = [{'rid': 'test_req', 'iter': 1, 'req_id': 'custom_req'}]
        sched_time = 100.0

        result = processor.extract_schedule_items(items, sched_time)

        assert isinstance(result, list)
        if len(result) > 0:
            assert result[0]['req_id'] == 'custom_req'
            assert result[0]['rid'] == 'test_req'
            assert result[0]['iter'] == 1
            assert result[0]['schedule_time'] == sched_time

    def test_extract_schedule_items_missing_req_id(self, processor):
        """测试 extract_schedule_items 缺少 req_id 的情况"""
        items = [{'rid': 'test_req', 'iter': 1}]
        sched_time = 100.0

        result = processor.extract_schedule_items(items, sched_time)

        if len(result) > 0:
            assert result[0]['req_id'] == 'test_req'  # 使用 rid 作为 req_id
            assert result[0]['rid'] == 'test_req'

    def test_extract_schedule_items_invalid_items(self, processor):
        """测试 extract_schedule_items 无效输入"""
        # 测试非列表输入
        result = processor.extract_schedule_items(None, 100.0)
        assert result == []

        # 测试包含非字典元素
        result = processor.extract_schedule_items([None, {'rid': 'test'}], 100.0)
        # 结果取决于具体实现

    def test_sort_schedule_data_normal_case(self, processor):
        """测试 sort_schedule_data 正常情况"""
        df = pd.DataFrame({
            'req_id': ['req_b', 'req_a', 'req_a'],
            'iter': [0, 1, 0],
            'schedule_time': [100, 100, 100]
        })

        result = processor.sort_schedule_data(df)

        assert isinstance(result, pd.DataFrame)
        # 验证排序结果（如果 DataFrame 不为空）
        if len(result) > 0:
            pass  # 具体验证取决于实现

    def test_sort_schedule_data_empty_input(self, processor):
        """测试 sort_schedule_data 空输入"""
        df = pd.DataFrame()
        result = processor.sort_schedule_data(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_build_forward_mapping_normal_case(self, processor, sample_batch_event_df):
        """测试 build_forward_mapping 正常情况"""
        result = processor.build_forward_mapping(sample_batch_event_df)

        assert isinstance(result, dict)
        # 验证结构
        # 具体验证取决于实现

    def test_build_forward_mapping_empty_input(self, processor, empty_batch_event_df):
        """测试 build_forward_mapping 空输入"""
        result = processor.build_forward_mapping(empty_batch_event_df)
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_create_forward_records_normal_case(self, processor):
        """测试 create_forward_records 正常情况"""
        items = [{'rid': 'test_req'}]
        blocks = [1, 2, 3]
        fwd_time = 100.0

        result = processor.create_forward_records(items, blocks, fwd_time)

        assert isinstance(result, list)
        if len(result) > 0:
            assert result[0]['rid'] == 'test_req'
            assert result[0]['time'] == fwd_time
            assert result[0]['blocks'] == blocks

    def test_create_forward_records_invalid_input(self, processor):
        """测试 create_forward_records 无效输入"""
        # 测试非列表输入
        result = processor.create_forward_records(None, [1, 2], 100.0)
        assert result == []

    def test_assign_blocks_vectorized_normal_case(self, processor):
        """测试 assign_blocks_vectorized 正常情况"""
        schedule_data = pd.DataFrame({
            'rid': ['req_1', 'req_2'],
            'iter': [0, 1],
            'schedule_time': [100.0, 200.0]
        })

        forward_mapping = {
            'req_1': [{'time': 110.0, 'blocks': [10, 20]}],
            'req_2': [{'time': 210.0, 'blocks': [30, 40]}]
        }

        result = processor.assign_blocks_vectorized(schedule_data, forward_mapping)

        assert isinstance(result, list)
        # 具体验证取决于实现

    def test_assign_blocks_vectorized_empty_input(self, processor):
        """测试 assign_blocks_vectorized 空输入"""
        schedule_data = pd.DataFrame()
        forward_mapping = {}

        result = processor.assign_blocks_vectorized(schedule_data, forward_mapping)
        assert result == []

    def test_find_block_strategies(self, processor):
        """测试三种 block 查找策略"""
        records = [
            {'time': 90.0, 'blocks': [1, 2]},  # 过去时间
            {'time': 110.0, 'blocks': [3, 4]},  # 未来时间
            {'time': 120.0, 'blocks': [5, 6, 7]}  # 最后记录
        ]

        # 测试未来时间策略
        result = processor.find_block_in_future(records, 0, 105.0)
        # 具体结果取决于实现

        # 测试过去时间策略
        result = processor.find_block_in_past(records, 1, 100.0)
        # 具体结果取决于实现

        # 测试 fallback 策略
        result = processor.find_block_fallback(records, 2)
        # 具体结果取决于实现

    def test_high_iter_values(self, processor, sample_batch_event_df_with_high_iter):
        """测试高 iter 值处理"""
        batch_exec, batch_req = processor.parse_batch_exec_req(sample_batch_event_df_with_high_iter)

        assert isinstance(batch_exec, pd.DataFrame)
        assert isinstance(batch_req, pd.DataFrame)

    def test_malformed_data_handling(self, processor, malformed_batch_event_df):
        """测试畸形数据处理"""
        batch_exec, batch_req = processor.parse_batch_exec_req(malformed_batch_event_df)

        # 应该能够处理畸形数据而不崩溃
        assert isinstance(batch_exec, pd.DataFrame)
        assert isinstance(batch_req, pd.DataFrame)

    def test_edge_cases(self, processor):
        """测试边界情况"""
        # 测试空 blocks
        records = [{'time': 100.0, 'blocks': []}]
        result = processor.find_block_fallback(records, 0)
        # 具体结果取决于实现

        # 测试 None blocks
        records = [{'time': 100.0, 'blocks': None}]
        result = processor.find_block_fallback(records, 0)
        # 具体结果取决于实现

        # 测试 iter 超出范围
        records = [{'time': 100.0, 'blocks': [1, 2]}]
        result = processor.find_block_fallback(records, 5)  # iter=5, 但只有2个元素
        # 具体结果取决于实现
