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

from types import SimpleNamespace

import ms_service_metric.adapters.vllm.handlers.meta_handlers as mh
import ms_service_metric.adapters.vllm.handlers.utils as hu


class _FakeState:
    def __init__(self, dp_rank=-1, has_dp=False):
        self.dp_rank = dp_rank
        self._has_dp = has_dp

    def has(self, name):
        return name == "dp_rank" and self._has_dp


def test_given_engine_side_dp_rank_when_init_data_parallel_then_meta_state_updated(monkeypatch):
    state = _FakeState(dp_rank=-1, has_dp=False)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)

    this = SimpleNamespace(dp_rank=7)
    ret = mh.init_data_parallel(lambda *_a, **_k: "ok", this, object())
    assert ret == "ok"
    assert state.dp_rank == 7


def test_given_worker_side_no_dp_rank_when_collect_then_fallback_to_parallel_config(monkeypatch):
    state = _FakeState(dp_rank=-1, has_dp=False)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)

    worker = SimpleNamespace(parallel_config=SimpleNamespace(data_parallel_rank=3))
    mh.ensure_dp_rank_meta_collected(worker)
    assert state.dp_rank == 3


def test_given_dp_already_collected_when_collect_then_no_change(monkeypatch):
    state = _FakeState(dp_rank=9, has_dp=True)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)

    worker = SimpleNamespace(dp_rank=1)
    mh.ensure_dp_rank_meta_collected(worker)
    assert state.dp_rank == 9


def test_given_make_stats_when_called_then_records_kv_metrics_and_injects_dp(monkeypatch):
    state = _FakeState(dp_rank=5, has_dp=True)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)
    mock_client = SimpleNamespace(calls=[])
    mock_client.record_metric = lambda *a, **k: mock_client.calls.append((a, k))
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    pool = SimpleNamespace(num_gpu_blocks=100, get_num_free_blocks=lambda: 40)
    phase_state = SimpleNamespace(request_id_to_prompt_token_len={})
    monkeypatch.setattr(mh, "get_scheduler_phase_state", lambda: phase_state)
    this = SimpleNamespace(
        kv_cache_manager=SimpleNamespace(block_pool=pool),
        running=[],
        waiting=[],
    )
    ret_obj = SimpleNamespace(kv_connector_stats=None)

    out = mh.make_stats(lambda *_a, **_k: ret_obj, this)

    assert out is ret_obj
    assert len(mock_client.calls) == 9
    assert ret_obj.kv_connector_stats["dp"] == 5
    kv_calls = [
        kwargs["labels"]
        for args, kwargs in mock_client.calls
        if args and args[0] in (mh.TOTAL_KVCACHE_BLOCKS, mh.FREE_KVCACHE_BLOCKS, mh.ALLOCATED_KVCACHE_BLOCKS)
    ]
    assert kv_calls == [
        {"dp": 5, "phase": "all"},
        {"dp": 5, "phase": "all"},
        {"dp": 5, "phase": "all"},
    ]


def test_given_existing_kv_connector_stats_when_make_stats_then_dp_is_merged(monkeypatch):
    state = _FakeState(dp_rank=2, has_dp=True)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: None)
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    pool = SimpleNamespace(num_gpu_blocks=8, get_num_free_blocks=lambda: 3)
    phase_state = SimpleNamespace(request_id_to_prompt_token_len={})
    monkeypatch.setattr(mh, "get_scheduler_phase_state", lambda: phase_state)
    this = SimpleNamespace(
        kv_cache_manager=SimpleNamespace(block_pool=pool),
        running=[],
        waiting=[],
    )
    ret_obj = SimpleNamespace(kv_connector_stats={"x": 1})

    mh.make_stats(lambda *_a, **_k: ret_obj, this)
    assert ret_obj.kv_connector_stats["x"] == 1
    assert ret_obj.kv_connector_stats["dp"] == 2


def test_given_queue_phase_counts_when_make_stats_then_records_running_and_waiting_phase_metrics(monkeypatch):
    state = _FakeState(dp_rank=4, has_dp=True)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    phase_state = hu.SchedulerPhaseState()
    monkeypatch.setattr(mh, "get_scheduler_phase_state", lambda: phase_state)

    running_prefill = SimpleNamespace(request_id="run_prefill", prompt_token_ids=[1, 2, 3], num_computed_tokens=1)
    running_decode = SimpleNamespace(request_id="run_decode", prompt_token_ids=[1, 2], num_computed_tokens=2)
    waiting_decode = SimpleNamespace(request_id="wait_decode")
    waiting_decode.request = SimpleNamespace(num_computed_tokens=4)
    waiting_unknown = SimpleNamespace(request_id="wait_unknown", prompt_token_ids=[1, 2, 3])
    phase_state.request_id_to_prompt_token_len["wait_decode"] = 4

    pool = SimpleNamespace(num_gpu_blocks=10, get_num_free_blocks=lambda: 2)
    this = SimpleNamespace(
        kv_cache_manager=SimpleNamespace(block_pool=pool),
        running=[running_prefill, running_decode],
        waiting=[waiting_decode, waiting_unknown],
    )
    ret_obj = SimpleNamespace(kv_connector_stats=None)

    mh.make_stats(lambda *_a, **_k: ret_obj, this)

    phase_values = {
        (args[0], kwargs["labels"]["req_phase"]): kwargs["value"]
        for args, kwargs in recorded
        if len(args) >= 1 and isinstance(kwargs.get("labels"), dict) and "req_phase" in kwargs["labels"]
    }

    assert phase_values[(mh.RUNNING_PHASE_BATCH_SIZE, "prefill")] == 1
    assert phase_values[(mh.RUNNING_PHASE_BATCH_SIZE, "decode")] == 1
    assert phase_values[(mh.RUNNING_PHASE_BATCH_SIZE, "unknown")] == 0
    assert phase_values[(mh.WAITING_PHASE_BATCH_SIZE, "prefill")] == 0
    assert phase_values[(mh.WAITING_PHASE_BATCH_SIZE, "decode")] == 1
    assert phase_values[(mh.WAITING_PHASE_BATCH_SIZE, "unknown")] == 1


def test_given_missing_queue_when_collect_queue_phase_metrics_then_returns_zero_counts():
    phase_state = hu.SchedulerPhaseState()

    phase_values = hu.collect_queue_phase_metrics(phase_state, None)

    assert phase_values == {"prefill": 0, "decode": 0, "unknown": 0}


def test_given_scheduler_missing_queue_attr_when_get_scheduler_queue_then_warns_once(monkeypatch):
    warnings = []
    monkeypatch.setattr(mh.logger, "warning", lambda *a, **k: warnings.append((a, k)))
    mh._MISSING_QUEUE_ATTRS_WARNED.clear()

    scheduler = SimpleNamespace()

    assert mh._get_scheduler_queue(scheduler, "running") == []
    assert mh._get_scheduler_queue(scheduler, "running") == []
    assert len(warnings) == 1
    assert "running" in warnings[0][0]


def test_given_pid_changes_when_get_scheduler_phase_state_then_state_is_reinitialized(monkeypatch):
    if hasattr(hu._scheduler_phase_state, "state"):
        del hu._scheduler_phase_state.state

    monkeypatch.setattr(hu.os, "getpid", lambda: 100)

    first = hu.get_scheduler_phase_state()
    first.request_id_to_prompt_token_len["stale"] = 1
    same = hu.get_scheduler_phase_state()

    monkeypatch.setattr(hu.os, "getpid", lambda: 200)
    changed = hu.get_scheduler_phase_state()

    assert same is first
    assert changed is not first
    assert changed.request_id_to_prompt_token_len == {}


def test_given_num_prompt_tokens_without_prompt_token_ids_when_make_stats_then_prefill_is_classified(monkeypatch):
    state = _FakeState(dp_rank=1, has_dp=True)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    phase_state = hu.SchedulerPhaseState()
    monkeypatch.setattr(mh, "get_scheduler_phase_state", lambda: phase_state)

    running_prefill = SimpleNamespace(
        request_id="run_prefill_num_prompt_only",
        num_prompt_tokens=6,
        prompt_token_ids=None,
        num_computed_tokens=2,
    )

    pool = SimpleNamespace(num_gpu_blocks=10, get_num_free_blocks=lambda: 2)
    this = SimpleNamespace(
        kv_cache_manager=SimpleNamespace(block_pool=pool),
        running=[running_prefill],
        waiting=[],
    )
    ret_obj = SimpleNamespace(kv_connector_stats=None)

    mh.make_stats(lambda *_a, **_k: ret_obj, this)

    phase_values = {
        (args[0], kwargs["labels"]["req_phase"]): kwargs["value"]
        for args, kwargs in recorded
        if len(args) >= 1 and isinstance(kwargs.get("labels"), dict) and "req_phase" in kwargs["labels"]
    }

    assert phase_values[(mh.RUNNING_PHASE_BATCH_SIZE, "prefill")] == 1
    assert phase_values[(mh.RUNNING_PHASE_BATCH_SIZE, "decode")] == 0
    assert phase_values[(mh.RUNNING_PHASE_BATCH_SIZE, "unknown")] == 0


def test_given_scheduler_stats_when_record_then_scheduler_and_iteration_metrics_recorded(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    scheduler_stats = SimpleNamespace(
        num_running_reqs=4,
        num_waiting_reqs=1,
        spec_decoding_stats=SimpleNamespace(num_spec_tokens=11),
    )
    iteration_stats = SimpleNamespace(
        num_prompt_tokens=5,
        num_generation_tokens=7,
        inter_token_latencies_iter=[0.02],
        time_to_first_tokens_iter=[0.11, 0.12],
        finished_requests=[SimpleNamespace(mean_time_per_output_token=0.9)],
    )

    out = mh.record(
        lambda *_a, **_k: "ret",
        object(),
        scheduler_stats,
        iteration_stats,
        None,
        "eng0",
    )
    assert out == "ret"
    assert len(recorded) >= 8


def test_given_slow_decode_and_prefill_when_update_from_output_then_threshold_counters_recorded(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)
    monkeypatch.setattr(mh, "get_meta_state", lambda: _FakeState(dp_rank=8, has_dp=True))

    iteration_stats = SimpleNamespace(
        inter_token_latencies_iter=[0.5, 1.0, 1.2, 2.0],
        time_to_first_tokens_iter=[4.9, 5.1, 10.1, 20.1],
    )
    req_stats = SimpleNamespace(num_generation_tokens=0, last_token_ts=10.0)

    out = mh.iteration_stats_update_from_output_hooker(
        lambda *_a, **_k: "ok",
        iteration_stats,
        SimpleNamespace(request_id="rid"),
        10.25,
        False,
        8,
        req_stats,
        None,
        None,
    )

    assert out == "ok"
    assert ((mh.DECODE_OVER_1S_COUNT, 2, {"phase": "all"}), {}) in recorded
    assert ((mh.PREFILL_OVER_THRESHOLD_COUNT, 3, {"threshold": "5s", "phase": "all"}), {}) in recorded
    assert ((mh.PREFILL_OVER_THRESHOLD_COUNT, 2, {"threshold": "10s", "phase": "all"}), {}) in recorded
    assert ((mh.PREFILL_OVER_THRESHOLD_COUNT, 1, {"threshold": "20s", "phase": "all"}), {}) in recorded


def test_given_empty_latency_lists_when_update_from_output_then_threshold_counters_not_recorded(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)
    monkeypatch.setattr(mh, "get_meta_state", lambda: _FakeState(dp_rank=8, has_dp=True))

    iteration_stats = SimpleNamespace(
        inter_token_latencies_iter=None,
        time_to_first_tokens_iter=[],
    )
    req_stats = SimpleNamespace(num_generation_tokens=0, last_token_ts=10.0)

    mh.iteration_stats_update_from_output_hooker(
        lambda *_a, **_k: "ok",
        iteration_stats,
        SimpleNamespace(request_id="rid"),
        10.25,
        False,
        8,
        req_stats,
        None,
        None,
    )

    metric_names = [args[0] for args, _kwargs in recorded]
    assert mh.DECODE_OVER_1S_COUNT not in metric_names
    assert mh.PREFILL_OVER_THRESHOLD_COUNT not in metric_names


def test_given_threshold_metric_record_fails_when_update_from_output_then_existing_metrics_continue(monkeypatch):
    recorded = []

    def record_metric(*args, **kwargs):
        if args[0] == mh.DECODE_OVER_1S_COUNT:
            raise RuntimeError("metrics down")
        recorded.append((args, kwargs))

    mock_client = SimpleNamespace(record_metric=record_metric)
    monkeypatch.setattr(mh, "metrics_client", mock_client)
    monkeypatch.setattr(mh, "get_meta_state", lambda: _FakeState(dp_rank=8, has_dp=True))

    iteration_stats = SimpleNamespace(
        inter_token_latencies_iter=[1.2],
        time_to_first_tokens_iter=[5.1],
    )
    req_stats = SimpleNamespace(num_generation_tokens=1, last_token_ts=10.0)

    out = mh.iteration_stats_update_from_output_hooker(
        lambda *_a, **_k: "ok",
        iteration_stats,
        SimpleNamespace(request_id="rid"),
        10.25,
        False,
        8,
        req_stats,
        None,
        None,
    )

    assert out == "ok"
    assert ((mh.PREFILL_OVER_THRESHOLD_COUNT, 1, {"threshold": "5s", "phase": "all"}), {}) in recorded
    assert ((mh.SECOND_TOKEN_LATENCY,), {"labels": {"dp": 8, "phase": "all"}, "value": 0.25}) in recorded


def test_given_none_stats_when_record_helpers_then_return_without_recording(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    mh._record_scheduler_metrics(None, {"engine": "e"})
    mh._record_iteration_metrics(None, {"engine": "e"})
    assert not recorded


def test_given_second_decode_output_when_update_from_output_then_records_second_token_latency(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)
    monkeypatch.setattr(mh, "get_meta_state", lambda: _FakeState(dp_rank=8, has_dp=True))

    req_stats = SimpleNamespace(num_generation_tokens=1, last_token_ts=10.0)

    out = mh.iteration_stats_update_from_output_hooker(
        lambda *_a, **_k: "ok",
        object(),
        SimpleNamespace(request_id="rid"),
        10.25,
        False,
        8,
        req_stats,
        None,
        None,
    )
    assert out == "ok"

    assert ((mh.SECOND_TOKEN_LATENCY,), {"labels": {"dp": 8, "phase": "all"}, "value": 0.25}) in recorded


def test_given_master_style_args_when_update_from_output_then_records_second_token_latency(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)
    monkeypatch.setattr(mh, "get_meta_state", lambda: _FakeState(dp_rank=6, has_dp=True))

    req_stats = SimpleNamespace(num_generation_tokens=1, last_token_ts=20.0)

    out = mh.iteration_stats_update_from_output_hooker(
        lambda *_a, **_k: "ok-master",
        object(),
        SimpleNamespace(request_id="rid-master"),
        20.5,
        False,
        req_stats,
        None,
        None,
    )
    assert out == "ok-master"
    assert ((mh.SECOND_TOKEN_LATENCY,), {"labels": {"dp": 6, "phase": "all"}, "value": 0.5}) in recorded


def test_given_prefill_or_later_decode_when_update_from_output_then_skip_second_token_latency(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    mh.iteration_stats_update_from_output_hooker(
        lambda *_a, **_k: "prefill",
        object(),
        SimpleNamespace(request_id="prefill"),
        10.25,
        True,
        8,
        SimpleNamespace(num_generation_tokens=1, last_token_ts=10.0),
        None,
        None,
    )
    mh.iteration_stats_update_from_output_hooker(
        lambda *_a, **_k: "later",
        object(),
        SimpleNamespace(request_id="later"),
        10.25,
        False,
        8,
        SimpleNamespace(num_generation_tokens=2, last_token_ts=10.0),
        None,
        None,
    )

    assert all(call[0][0] != mh.SECOND_TOKEN_LATENCY for call in recorded)


def test_given_kv_connector_stats_with_dp_when_record_dp_rank_then_meta_updated_and_temp_key_removed(monkeypatch):
    state = _FakeState(dp_rank=-1, has_dp=False)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)
    scheduler_stats = SimpleNamespace(kv_connector_stats={"dp": 6, "keep": 1})

    out = mh.record_dp_rank(lambda *_a, **_k: "done", object(), scheduler_stats)
    assert out == "done"
    assert state.dp_rank == 6
    assert scheduler_stats.kv_connector_stats == {"keep": 1}


def test_given_only_dp_in_kv_connector_stats_when_record_dp_rank_then_dict_becomes_none(monkeypatch):
    state = _FakeState(dp_rank=-1, has_dp=False)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)
    scheduler_stats = SimpleNamespace(kv_connector_stats={"dp": 4})

    mh.record_dp_rank(lambda *_a, **_k: None, object(), scheduler_stats)
    assert scheduler_stats.kv_connector_stats is None
