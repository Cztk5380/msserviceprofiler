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

from unittest.mock import MagicMock, patch

import pytest

from ms_service_profiler.patcher.vllm.handlers.v1 import meta_handlers


class TestMakeStats:
    """测试 make_stats hook 函数"""

    def test_make_stats_calls_original_and_records_kvcache_metrics(self):
        """make_stats 调用原函数并记录 kvcache 相关指标"""
        original_func = MagicMock(return_value=MagicMock(kv_connector_stats=None))
        this = MagicMock()
        this.kv_cache_manager.block_pool.num_gpu_blocks = 100
        this.kv_cache_manager.block_pool.get_num_free_blocks.return_value = 30

        with patch.object(meta_handlers, "MetricManager") as MockMM:
            with patch.object(meta_handlers, "_get_state") as mock_state:
                state = MagicMock()
                state.dp_rank_id = 0
                state.has_collected = True
                mock_state.return_value = state

                result = meta_handlers.make_stats(original_func, this)

                original_func.assert_called_once_with(this)
                assert result.kv_connector_stats is not None
                assert result.kv_connector_stats.get("dp") == 0
                assert MockMM.record_metric.call_count >= 3  # total, free, allocated

    def test_make_stats_sets_kv_connector_stats_on_ret(self):
        """make_stats 在返回对象上设置 kv_connector_stats 的 dp"""
        ret = MagicMock(kv_connector_stats={"other": "x"})
        original_func = MagicMock(return_value=ret)
        this = MagicMock()
        this.kv_cache_manager.block_pool.num_gpu_blocks = 10
        this.kv_cache_manager.block_pool.get_num_free_blocks.return_value = 5

        with patch.object(meta_handlers, "MetricManager"):
            with patch.object(meta_handlers, "_get_state") as mock_state:
                mock_state.return_value = MagicMock(dp_rank_id=1, has_collected=True)

                result = meta_handlers.make_stats(original_func, this)
                assert result.kv_connector_stats["dp"] == 1
                assert result.kv_connector_stats["other"] == "x"


class TestRecordSchedulerMetrics:
    """测试 _record_scheduler_metrics 函数"""

    def test_record_scheduler_metrics_none_stats_no_call(self):
        """scheduler_stats 为 None 时不调用 record_metric"""
        with patch.object(meta_handlers, "MetricManager") as MockMM:
            meta_handlers._record_scheduler_metrics(None, {"dp": "0"})
            MockMM.record_metric.assert_not_called()

    def test_record_scheduler_metrics_records_batch_and_waiting(self):
        """有 stats 时记录 BATCH_SIZE、WAITING_BATCH_SIZE"""
        scheduler_stats = MagicMock()
        scheduler_stats.num_running_reqs = 4
        scheduler_stats.num_waiting_reqs = 2
        scheduler_stats.spec_decoding_stats = None

        with patch.object(meta_handlers, "MetricManager") as MockMM:
            meta_handlers._record_scheduler_metrics(scheduler_stats, {"dp": "0", "engine": 0})
            calls = [c[0][0] for c in MockMM.record_metric.call_args_list]
            assert meta_handlers.MetricConstants.BATCH_SIZE in calls
            assert meta_handlers.MetricConstants.WAITING_BATCH_SIZE in calls

    def test_record_scheduler_metrics_records_num_spec_tokens_when_present(self):
        """有 spec_decoding_stats 且 num_spec_tokens 存在时记录 NUM_SPEC_TOKENS"""
        scheduler_stats = MagicMock()
        scheduler_stats.num_running_reqs = 0
        scheduler_stats.num_waiting_reqs = 0
        scheduler_stats.spec_decoding_stats = MagicMock(num_spec_tokens=10)

        with patch.object(meta_handlers, "MetricManager") as MockMM:
            meta_handlers._record_scheduler_metrics(scheduler_stats, {"dp": "0"})
            names = [c[0][0] for c in MockMM.record_metric.call_args_list]
            assert meta_handlers.MetricConstants.NUM_SPEC_TOKENS in names


class TestRecord:
    """测试 record hook 函数"""

    def test_record_calls_original_and_record_scheduler_metrics(self):
        """record 调用原函数并调用 _record_scheduler_metrics、_record_iteration_metrics"""
        original_func = MagicMock(return_value="ok")
        this = MagicMock()
        scheduler_stats = MagicMock()
        scheduler_stats.kv_connector_stats = {"dp": 0}
        iteration_stats = None
        mm_cache_stats = None
        engine_idx = 0

        with patch.object(meta_handlers, "_record_scheduler_metrics") as mock_sched:
            with patch.object(meta_handlers, "_record_iteration_metrics") as mock_iter:
                result = meta_handlers.record(
                    original_func, this,
                    scheduler_stats, iteration_stats, mm_cache_stats, engine_idx,
                )
                assert result == "ok"
                original_func.assert_called_once()
                mock_sched.assert_called_once()
                mock_iter.assert_called_once_with(iteration_stats, {"dp": 0, "engine": engine_idx})

    def test_record_pops_dp_from_kv_connector_stats(self):
        """record 会从 scheduler_stats.kv_connector_stats 中删除临时 dp（删空后会置为 None）"""
        original_func = MagicMock(return_value=None)
        scheduler_stats = MagicMock()
        scheduler_stats.kv_connector_stats = {"dp": 0}

        with patch.object(meta_handlers, "_record_scheduler_metrics"):
            with patch.object(meta_handlers, "_record_iteration_metrics"):
                meta_handlers.record(
                    original_func, MagicMock(),
                    scheduler_stats, None, None, 0,
                )
                # 删空后源码会将 kv_connector_stats 置为 None
                assert scheduler_stats.kv_connector_stats is None or "dp" not in scheduler_stats.kv_connector_stats


class TestEnsureDpRankMetaCollected:
    """测试 ensure_dp_rank_meta_collected 与 init_data_parallel_worker"""

    def test_ensure_dp_rank_meta_collected_skips_when_already_collected(self):
        """若已采集过则不再写入 Meta"""
        worker = MagicMock()
        worker.dp_rank = 1
        with patch.object(meta_handlers, "_get_state") as mock_state:
            state = MagicMock()
            state.has_collected = True
            mock_state.return_value = state
            with patch.object(meta_handlers, "Profiler") as MockProfiler:
                meta_handlers.ensure_dp_rank_meta_collected(worker)
                MockProfiler.return_value.add_meta_info.assert_not_called()

    def test_ensure_dp_rank_meta_collected_writes_when_not_collected_using_dp_rank(self):
        """未采集时从 worker.dp_rank 取并写入 Meta"""
        worker = MagicMock()
        worker.dp_rank = 2
        with patch.object(meta_handlers, "_get_state") as mock_state:
            state = MagicMock()
            state.has_collected = False
            mock_state.return_value = state
            with patch.object(meta_handlers, "get_hook_metrics") as mock_metrics:
                with patch.object(meta_handlers, "Profiler") as MockProfiler:
                    meta_handlers.ensure_dp_rank_meta_collected(worker)
                    MockProfiler.return_value.add_meta_info.assert_called_once_with("dpRankId", 2)
                    assert state.has_collected is True
                    assert state.dp_rank_id == 2
                    mock_metrics.return_value.meta_state = state

    def test_ensure_dp_rank_meta_collected_falls_back_to_parallel_config(self):
        """无 dp_rank 时从 parallel_config.data_parallel_rank 取"""
        worker = MagicMock()
        worker.dp_rank = None
        worker.parallel_config = MagicMock()
        worker.parallel_config.data_parallel_rank = 3
        with patch.object(meta_handlers, "_get_state") as mock_state:
            state = MagicMock()
            state.has_collected = False
            mock_state.return_value = state
            with patch.object(meta_handlers, "get_hook_metrics"):
                with patch.object(meta_handlers, "Profiler") as MockProfiler:
                    meta_handlers.ensure_dp_rank_meta_collected(worker)
                    MockProfiler.return_value.add_meta_info.assert_called_once_with("dpRankId", 3)
                    assert state.dp_rank_id == 3

    def test_ensure_dp_rank_meta_collected_uses_minus_one_when_no_source(self):
        """无 dp_rank 且无 parallel_config 时使用 -1"""
        worker = MagicMock()
        worker.dp_rank = None
        worker.parallel_config = None
        with patch.object(meta_handlers, "_get_state") as mock_state:
            state = MagicMock()
            state.has_collected = False
            mock_state.return_value = state
            with patch.object(meta_handlers, "get_hook_metrics"):
                with patch.object(meta_handlers, "Profiler") as MockProfiler:
                    meta_handlers.ensure_dp_rank_meta_collected(worker)
                    MockProfiler.return_value.add_meta_info.assert_called_once_with("dpRankId", -1)
                    assert state.dp_rank_id == -1

    def test_init_data_parallel_worker_calls_ensure_and_original(self):
        """init_data_parallel_worker 先调用 ensure_dp_rank_meta_collected 再调用原函数"""
        original_func = MagicMock(return_value="result")
        this = MagicMock()
        this.dp_rank = 0
        with patch.object(meta_handlers, "ensure_dp_rank_meta_collected") as mock_ensure:
            result = meta_handlers.init_data_parallel_worker(original_func, this, "a", k=1)
            mock_ensure.assert_called_once_with(this)
            original_func.assert_called_once_with(this, "a", k=1)
            assert result == "result"


class TestInitDataParallel:
    """测试 init_data_parallel hook（Engine 侧）"""

    def test_init_data_parallel_already_collected_does_not_add_meta(self):
        """若已采集过 dpRankId 则不调用 add_meta_info"""
        original_func = MagicMock(return_value="ok")
        this = MagicMock()
        this.dp_rank = 0
        vllm_config = MagicMock()
        with patch.object(meta_handlers, "_get_state") as mock_state:
            state = MagicMock()
            state.has_collected = True
            mock_state.return_value = state
            with patch.object(meta_handlers, "get_hook_metrics"):
                with patch.object(meta_handlers, "Profiler") as MockProfiler:
                    result = meta_handlers.init_data_parallel(original_func, this, vllm_config)
                    MockProfiler.return_value.add_meta_info.assert_not_called()
        assert result == "ok"

    def test_init_data_parallel_first_time_adds_meta_and_sets_state(self):
        """首次采集时调用 add_meta_info 并更新 state"""
        original_func = MagicMock(return_value="ok")
        this = MagicMock()
        this.dp_rank = 2
        vllm_config = MagicMock()
        with patch.object(meta_handlers, "_get_state") as mock_state:
            state = MagicMock()
            state.has_collected = False
            mock_state.return_value = state
            with patch.object(meta_handlers, "get_hook_metrics") as mock_metrics:
                with patch.object(meta_handlers, "Profiler") as MockProfiler:
                    result = meta_handlers.init_data_parallel(original_func, this, vllm_config)
                    MockProfiler.return_value.add_meta_info.assert_called_once_with("dpRankId", 2)
                    assert state.has_collected is True
                    assert state.dp_rank_id == 2
                    mock_metrics.return_value.meta_state = state
        assert result == "ok"


class TestRecordIterationMetrics:
    """测试 _record_iteration_metrics 分支覆盖"""

    def test_record_iteration_metrics_none_stats_no_call(self):
        with patch.object(meta_handlers, "MetricManager") as MockMM:
            meta_handlers._record_iteration_metrics(None, {"dp": "0"})
            MockMM.record_metric.assert_not_called()

    def test_record_iteration_metrics_total_tokens(self):
        iteration_stats = MagicMock()
        iteration_stats.num_prompt_tokens = 10
        iteration_stats.num_generation_tokens = 5
        iteration_stats.inter_token_latencies_iter = None
        iteration_stats.time_to_first_tokens_iter = None
        iteration_stats.finished_requests = None
        with patch.object(meta_handlers, "MetricManager") as MockMM:
            meta_handlers._record_iteration_metrics(iteration_stats, {"dp": "0"})
            names = [c[0][0] for c in MockMM.record_metric.call_args_list]
            assert meta_handlers.MetricConstants.TOTAL_TOKENS in names
            assert meta_handlers.MetricConstants.INPUT_METRICS in names
            assert meta_handlers.MetricConstants.OUTPUT_METRICS in names

    def test_record_iteration_metrics_second_token_latency(self):
        iteration_stats = MagicMock()
        iteration_stats.num_prompt_tokens = None
        iteration_stats.num_generation_tokens = None
        iteration_stats.inter_token_latencies_iter = [0.01, 0.02]
        iteration_stats.time_to_first_tokens_iter = None
        iteration_stats.finished_requests = None
        with patch.object(meta_handlers, "MetricManager") as MockMM:
            meta_handlers._record_iteration_metrics(iteration_stats, {"dp": "0"})
            names = [c[0][0] for c in MockMM.record_metric.call_args_list]
            assert meta_handlers.MetricConstants.SECOND_TOKEN_LATENCY in names

    def test_record_iteration_metrics_ttft_and_tpot(self):
        iteration_stats = MagicMock()
        iteration_stats.num_prompt_tokens = None
        iteration_stats.num_generation_tokens = None
        iteration_stats.inter_token_latencies_iter = None
        iteration_stats.time_to_first_tokens_iter = [0.1, 0.2]
        finished_req = MagicMock()
        finished_req.mean_time_per_output_token = 0.05
        iteration_stats.finished_requests = [finished_req]
        with patch.object(meta_handlers, "MetricManager") as MockMM:
            meta_handlers._record_iteration_metrics(iteration_stats, {"dp": "0"})
            names = [c[0][0] for c in MockMM.record_metric.call_args_list]
            assert meta_handlers.MetricConstants.FINE_GRAINED_TTFT in names
            assert meta_handlers.MetricConstants.FINE_GRAINED_TPOT in names


class TestRecordEdgeCases:
    """测试 record 边界分支"""

    def test_record_scheduler_stats_none_kv_stats_empty(self):
        """scheduler_stats 为 None 时 labels 使用 dp=-1"""
        original_func = MagicMock(return_value="ok")
        with patch.object(meta_handlers, "_record_scheduler_metrics") as mock_sched:
            with patch.object(meta_handlers, "_record_iteration_metrics") as mock_iter:
                result = meta_handlers.record(
                    original_func, MagicMock(),
                    None, None, None, 0,
                )
                assert result == "ok"
                mock_sched.assert_called_once_with(None, {"dp": -1, "engine": 0})

    def test_record_kv_connector_stats_none_then_labels_dp_minus_one(self):
        """scheduler_stats 非 None 但 kv_connector_stats 为 None"""
        original_func = MagicMock(return_value="ok")
        scheduler_stats = MagicMock()
        scheduler_stats.kv_connector_stats = None
        with patch.object(meta_handlers, "_record_scheduler_metrics") as mock_sched:
            with patch.object(meta_handlers, "_record_iteration_metrics"):
                result = meta_handlers.record(
                    original_func, MagicMock(),
                    scheduler_stats, None, None, 1,
                )
                mock_sched.assert_called_once_with(scheduler_stats, {"dp": -1, "engine": 1})

    def test_record_kv_connector_stats_only_dp_becomes_none_after_pop(self):
        """kv_connector_stats 仅含 dp 时 pop 后变为空字典，源码会置为 None"""
        original_func = MagicMock(return_value="ok")
        scheduler_stats = MagicMock()
        scheduler_stats.kv_connector_stats = {"dp": 0}
        with patch.object(meta_handlers, "_record_scheduler_metrics"):
            with patch.object(meta_handlers, "_record_iteration_metrics"):
                meta_handlers.record(
                    original_func, MagicMock(),
                    scheduler_stats, None, None, 0,
                )
                assert scheduler_stats.kv_connector_stats is None

    def test_record_kv_connector_stats_has_other_key_after_pop_dp_remains_dict(self):
        """kv_connector_stats 含其他 key 时 pop dp 后仍为 dict"""
        original_func = MagicMock(return_value="ok")
        scheduler_stats = MagicMock()
        scheduler_stats.kv_connector_stats = {"dp": 0, "other": "x"}
        with patch.object(meta_handlers, "_record_scheduler_metrics"):
            with patch.object(meta_handlers, "_record_iteration_metrics"):
                meta_handlers.record(
                    original_func, MagicMock(),
                    scheduler_stats, None, None, 0,
                )
                assert scheduler_stats.kv_connector_stats == {"other": "x"}
