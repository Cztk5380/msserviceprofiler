# -------------------------------------------------------------------------
# Unit tests for ms_service_profiler.patcher.vllm.handlers.v1.meta_handlers
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
