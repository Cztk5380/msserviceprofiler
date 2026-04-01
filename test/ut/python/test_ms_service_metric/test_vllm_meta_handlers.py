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
    this = SimpleNamespace(kv_cache_manager=SimpleNamespace(block_pool=pool))
    ret_obj = SimpleNamespace(kv_connector_stats=None)

    out = mh.make_stats(lambda *_a, **_k: ret_obj, this)

    assert out is ret_obj
    assert len(mock_client.calls) == 3
    assert ret_obj.kv_connector_stats["dp"] == 5


def test_given_existing_kv_connector_stats_when_make_stats_then_dp_is_merged(monkeypatch):
    state = _FakeState(dp_rank=2, has_dp=True)
    monkeypatch.setattr(mh, "get_meta_state", lambda: state)
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: None)
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    pool = SimpleNamespace(num_gpu_blocks=8, get_num_free_blocks=lambda: 3)
    this = SimpleNamespace(kv_cache_manager=SimpleNamespace(block_pool=pool))
    ret_obj = SimpleNamespace(kv_connector_stats={"x": 1})

    mh.make_stats(lambda *_a, **_k: ret_obj, this)
    assert ret_obj.kv_connector_stats["x"] == 1
    assert ret_obj.kv_connector_stats["dp"] == 2


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


def test_given_none_stats_when_record_helpers_then_return_without_recording(monkeypatch):
    recorded = []
    mock_client = SimpleNamespace(record_metric=lambda *a, **k: recorded.append((a, k)))
    monkeypatch.setattr(mh, "metrics_client", mock_client)

    mh._record_scheduler_metrics(None, {"engine": "e"})
    mh._record_iteration_metrics(None, {"engine": "e"})
    assert recorded == []


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
