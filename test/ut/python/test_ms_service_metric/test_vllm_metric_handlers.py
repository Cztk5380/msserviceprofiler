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
import asyncio

import ms_service_metric.adapters.vllm.handlers.metric_handlers as mh
import ms_service_metric.adapters.vllm.handlers.utils as hu
from ms_service_metric.metrics.metrics_manager import MetricConfig, MetricType


def _make_time_mock(values):
    remaining = list(values)

    def _mock_time():
        if remaining:
            return remaining.pop(0)
        return values[-1]

    return _mock_time


def test_given_phase_all_handler_when_called_then_records_fixed_phase(monkeypatch):
    calls = []
    manager = SimpleNamespace(
        get_or_create_metric=lambda *a, **k: None,
        record_metric=lambda *a, **k: calls.append((a, k)),
    )
    monkeypatch.setattr(mh, "get_metrics_manager", lambda: manager)
    monkeypatch.setattr(mh.time, "time", _make_time_mock([1.0, 1.25]))

    handler = mh.phase_all_handler([{"name": "plain:duration", "type": "timer"}])

    assert handler(lambda: "ok") == "ok"
    assert calls == [(("plain:duration", 0.25, {"phase": "all"}), {})]


def _make_scheduler_ret():
    return SimpleNamespace(
        num_scheduled_tokens=[],
        scheduled_new_reqs=[],
        scheduled_cached_reqs=SimpleNamespace(num_computed_tokens=[]),
        total_num_scheduled_tokens=0,
    )


def test_given_timeline_start_and_trigger_points_when_record_then_duration_metric_emitted(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=lambda *a, **k: calls.append((a, k)),
            get_or_create_metric=lambda *a, **k: None,
        ),
    )

    tl = mh.Timeline()
    tl.record("forward", 10.0, 1.0)
    tl.record("model_runner_get_output", 20.0, 2.0)

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == "npu:forward_duration"
    assert kwargs == {}


def test_given_model_runner_output_and_post_process_when_record_then_non_forward_metric_emitted(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=lambda *a, **k: calls.append((a, k)),
            get_or_create_metric=lambda *a, **k: None,
        ),
    )

    tl = mh.Timeline()
    tl.record("forward", 10.0, 1.0)
    tl.record("model_runner_get_output", 15.0, 2.0)
    tl.record("post process", 18.0, 4.0)

    metric_values = {args[0]: args[1] for args, _kwargs in calls}
    assert metric_values["npu:kernel_launch"] == 12.0
    assert metric_values["npu:non_forward_duration"] == 5.0


def test_given_negative_non_forward_duration_when_record_then_metric_skipped(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=lambda *a, **k: calls.append((a, k)),
            get_or_create_metric=lambda *a, **k: None,
        ),
    )

    tl = mh.Timeline()
    tl.record("model_runner_get_output", 20.0, 5.0)
    tl.record("post process", 18.0, 1.0)

    metric_names = [args[0] for args, _kwargs in calls]
    assert "npu:non_forward_duration" not in metric_names


def test_given_timing_context_normal_exit_when_exit_then_records_metric_and_timeline(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    tr_calls = []
    monkeypatch.setattr(mh, "timeline_recorder", SimpleNamespace(record=lambda *a, **k: tr_calls.append((a, k))))
    # __enter__ takes start time, __exit__ takes end time — fixed sequence, no coupling to record_metric calls.
    monkeypatch.setattr(mh.time, "time", _make_time_mock([100.0, 101.5]))

    class _Ctx:
        def __enter__(self):
            return "ctx"

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    with _Ctx() as ctx:
        assert ctx == "ctx"

    tcm = mh.TimingContextManager("abc", _Ctx())
    with tcm as ctx:
        assert ctx == "ctx"
    assert len(calls) == 1
    assert len(tr_calls) == 1


def test_given_timing_context_exception_when_exit_then_skip_metric(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    class _Ctx:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    with _Ctx():
        pass

    tcm = mh.TimingContextManager("abc", _Ctx())
    try:
        with tcm:
            raise RuntimeError("x")
    except RuntimeError as exc:
        assert str(exc) == "x"
    else:
        raise AssertionError("expected RuntimeError")
    assert not calls


def test_given_original_context_factory_when_hook_wrapped_then_returns_timing_context():
    out = mh.record_function_timer_hook(
        lambda name, *a, **k: SimpleNamespace(__enter__=lambda: None, __exit__=lambda *_: False), "n"
    )
    assert isinstance(out, mh.TimingContextManager)


def test_given_original_context_factory_with_self_when_ascend_hook_wrapped_then_returns_timing_context():
    out = mh.record_function_timer_hook_vllm_ascend(
        lambda _self, name, *a, **k: SimpleNamespace(__enter__=lambda: None, __exit__=lambda *_: False),
        object(),
        "n",
    )
    assert isinstance(out, mh.TimingContextManager)


def test_given_runner_get_output_when_hook_called_then_records_duration_and_timeline(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    tr_calls = []
    monkeypatch.setattr(mh, "timeline_recorder", SimpleNamespace(record=lambda *a, **k: tr_calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([10.0, 10.4]))

    out = mh.runner_get_output_hooker(lambda *_a, **_k: 123)
    assert out == 123
    assert len(calls) == 1
    assert len(tr_calls) == 1


def test_given_scheduler_result_when_scheduler_hook_called_then_records_core_metrics(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([1.0, 1.2, 1.2]))

    ret = SimpleNamespace(
        num_scheduled_tokens=[1, 2],
        scheduled_new_reqs=[SimpleNamespace(num_computed_tokens=3)],
        scheduled_cached_reqs=SimpleNamespace(num_computed_tokens=[4, 5]),
        total_num_scheduled_tokens=6,
    )
    scheduler = SimpleNamespace(running=[1, 2, 3])

    out = mh.scheduler_scheduler_hooker(lambda *_a, **_k: ret, scheduler)
    assert out is ret
    assert len(calls) >= 5
    metric_names = [a[0] for a, _k in calls]
    assert "scheduler:seqlen:sum" in metric_names


def test_given_scheduled_tokens_without_request_ids_when_scheduler_hook_called_then_records_unknown_phase(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([1.0, 1.2, 1.2]))

    ret = SimpleNamespace(
        num_scheduled_tokens=[1, 2],
        scheduled_new_reqs=[],
        scheduled_cached_reqs=SimpleNamespace(num_computed_tokens=[]),
        total_num_scheduled_tokens=3,
        finished_req_ids=[],
    )
    scheduler = SimpleNamespace(running=[])

    mh.scheduler_scheduler_hooker(lambda *_a, **_k: ret, scheduler)

    phase_values = {
        (args[0], args[2]["req_phase"]): args[1]
        for args, _kwargs in calls
        if len(args) >= 3 and isinstance(args[2], dict) and "req_phase" in args[2]
    }
    assert phase_values[("scheduler:phase_batch_size", "unknown")] == 2
    assert phase_values[("scheduler:phase_scheduled_tokens", "unknown")] == 3
    assert phase_values[("scheduler:phase_scheduled_token_counter", "unknown")] == 3


def test_given_scheduler_result_without_tokens_when_scheduler_hook_called_then_avg_sum_not_recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([2.0, 2.1]))

    ret = SimpleNamespace(
        num_scheduled_tokens=[],
        scheduled_new_reqs=[],
        scheduled_cached_reqs=SimpleNamespace(num_computed_tokens=[]),
        total_num_scheduled_tokens=0,
    )
    scheduler = SimpleNamespace(running=[])
    mh.scheduler_scheduler_hooker(lambda *_a, **_k: ret, scheduler)
    metric_names = [a[0] for a, _k in calls]
    assert "scheduler:seqlen:avg" not in metric_names
    assert "scheduler:seqlen:sum" not in metric_names
    assert "scheduler:phase_scheduled_token_counter" not in metric_names
    assert "scheduler:phase_scheduled_tokens" not in metric_names


def test_given_running_full_and_waiting_when_scheduler_hook_called_then_records_pending_once(monkeypatch):
    calls = []
    call_count = {"original": 0}
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([2.0, 2.1]))

    ret = _make_scheduler_ret()
    scheduler = SimpleNamespace(running=[1, 2], max_num_running_reqs=2, waiting=[object()], skipped_waiting=[])

    def original(*_args, **_kwargs):
        call_count["original"] += 1
        return ret

    out = mh.scheduler_scheduler_hooker(original, scheduler)

    assert out is ret
    assert call_count["original"] == 1
    assert ((mh.REQUEST_PREFILL_PENDING_NUMS, 1, {"phase": "all"}), {}) in calls


def test_given_running_full_and_only_skipped_waiting_when_scheduler_hook_called_then_records_pending(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([2.0, 2.1]))

    scheduler = SimpleNamespace(running=[1], max_num_running_reqs=1, waiting=[], skipped_waiting=[object()])

    mh.scheduler_scheduler_hooker(lambda *_a, **_k: _make_scheduler_ret(), scheduler)

    assert ((mh.REQUEST_PREFILL_PENDING_NUMS, 1, {"phase": "all"}), {}) in calls


def test_given_running_not_full_or_missing_attrs_when_scheduler_hook_called_then_does_not_record_pending(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([2.0, 2.1, 3.0, 3.1]))

    mh.scheduler_scheduler_hooker(
        lambda *_a, **_k: _make_scheduler_ret(),
        SimpleNamespace(running=[1], max_num_running_reqs=2, waiting=[object()]),
    )
    mh.scheduler_scheduler_hooker(lambda *_a, **_k: _make_scheduler_ret(), SimpleNamespace(running=[1]))

    assert not [call for call in calls if call[0][0] == mh.REQUEST_PREFILL_PENDING_NUMS]


def test_given_pending_metric_record_fails_when_scheduler_hook_called_then_original_result_returned(monkeypatch):
    call_count = {"original": 0}
    recorded = []

    def record_metric(*args, **kwargs):
        if args[0] == mh.REQUEST_PREFILL_PENDING_NUMS:
            raise RuntimeError("metrics down")
        recorded.append((args, kwargs))

    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=record_metric))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([2.0, 2.1]))

    ret = _make_scheduler_ret()
    scheduler = SimpleNamespace(running=[1], max_num_running_reqs=1, waiting=[object()])

    def original(*_args, **_kwargs):
        call_count["original"] += 1
        return ret

    out = mh.scheduler_scheduler_hooker(original, scheduler)

    assert out is ret
    assert call_count["original"] == 1
    assert any(args[0] == "scheduler:duration" for args, _kwargs in recorded)


def test_given_engine_core_scheduler_blocked_when_step_hook_called_then_records_pending(monkeypatch):
    calls = []
    call_count = {"original": 0}
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    ret = object()
    scheduler = SimpleNamespace(running=[1], max_num_running_reqs=1, waiting=[object()], skipped_waiting=[])
    engine_core = SimpleNamespace(scheduler=scheduler)

    def original(*_args, **_kwargs):
        call_count["original"] += 1
        return ret

    out = mh.engine_core_pending_hooker(original, engine_core)

    assert out is ret
    assert call_count["original"] == 1
    assert calls == [((mh.REQUEST_PREFILL_PENDING_NUMS, 1, {"phase": "all"}), {})]


def test_given_step_and_scheduler_run_in_same_cycle_when_pending_blocked_then_records_once(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(mh.time, "time", _make_time_mock([1.0, 1.1]))

    ret = _make_scheduler_ret()
    scheduler = SimpleNamespace(running=[1], max_num_running_reqs=1, waiting=[object()], skipped_waiting=[])
    engine_core = SimpleNamespace(scheduler=scheduler)

    assert mh.engine_core_pending_hooker(lambda *_a, **_k: "step", engine_core) == "step"
    assert mh.scheduler_scheduler_hooker(lambda *_a, **_k: ret, scheduler) is ret

    pending_calls = [entry for entry in calls if entry[0][0] == mh.REQUEST_PREFILL_PENDING_NUMS]
    assert pending_calls == [((mh.REQUEST_PREFILL_PENDING_NUMS, 1, {"phase": "all"}), {})]


def test_given_engine_core_without_blocked_scheduler_when_step_hook_called_then_does_not_record(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    scheduler = SimpleNamespace(running=[], max_num_running_reqs=1, waiting=[object()])
    engine_core = SimpleNamespace(scheduler=scheduler)

    out = mh.engine_core_pending_hooker(lambda *_a, **_k: "ok", engine_core)

    assert out == "ok"
    assert not calls


def test_given_engine_core_pending_metric_fails_when_step_hook_called_then_original_result_returned(monkeypatch):
    call_count = {"original": 0}

    def record_metric(*_args, **_kwargs):
        raise RuntimeError("metrics down")

    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=record_metric))

    scheduler = SimpleNamespace(running=[1], max_num_running_reqs=1, waiting=[object()])
    engine_core = SimpleNamespace(scheduler=scheduler)

    def original(*_args, **_kwargs):
        call_count["original"] += 1
        return "ok"

    out = mh.engine_core_pending_hooker(original, engine_core)

    assert out == "ok"
    assert call_count["original"] == 1


def test_given_mixed_phase_batch_when_scheduler_hook_called_then_prefill_decode_metrics_split(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    monkeypatch.setattr(
        mh,
        "_get_scheduler_phase_state",
        lambda: SimpleNamespace(request_id_to_prompt_token_len={"cached_prefill": 10}),
    )
    monkeypatch.setattr(mh.time, "time", _make_time_mock([3.0, 3.2]))

    ret = SimpleNamespace(
        num_scheduled_tokens={
            "new_prefill": 5,
            "new_decode": 2,
            "cached_prefill": 7,
        },
        scheduled_new_reqs=[
            SimpleNamespace(req_id="new_prefill", prompt_token_ids=list(range(8)), num_computed_tokens=3),
            SimpleNamespace(req_id="new_decode", prompt_token_ids=list(range(6)), num_computed_tokens=6),
        ],
        scheduled_cached_reqs=SimpleNamespace(
            req_ids=["cached_prefill"],
            num_computed_tokens=[4],
        ),
        total_num_scheduled_tokens=14,
        finished_req_ids=[],
    )
    scheduler = SimpleNamespace(running=[1, 2])

    out = mh.scheduler_scheduler_hooker(lambda *_a, **_k: ret, scheduler)
    assert out is ret

    phase_values = {
        (args[0], args[2]["req_phase"]): args[1]
        for args, _kwargs in calls
        if len(args) >= 3 and isinstance(args[2], dict) and "req_phase" in args[2]
    }

    assert phase_values[("scheduler:phase_batch_size", "prefill")] == 2
    assert phase_values[("scheduler:phase_batch_size", "decode")] == 1
    assert phase_values[("scheduler:phase_scheduled_token_counter", "prefill")] == 12
    assert phase_values[("scheduler:phase_scheduled_token_counter", "decode")] == 2
    assert phase_values[("scheduler:phase_scheduled_tokens", "prefill")] == 12
    assert phase_values[("scheduler:phase_scheduled_tokens", "decode")] == 2


def test_given_v1_preempt_request_when_hook_called_then_records_exact_recompute_event(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    phase_state = hu.SchedulerPhaseState()
    phase_state.request_id_to_prompt_token_len["r1"] = 8
    monkeypatch.setattr(mh, "_get_scheduler_phase_state", lambda: phase_state)

    out = mh.scheduler_preempt_request_hooker(lambda *_a, **_k: "ok", object(), SimpleNamespace(request_id="r1"))

    assert out == "ok"
    assert "r1" not in phase_state.request_id_to_prompt_token_len
    assert (("running_to_waiting_count", 1, {"phase": "all"}), {}) in calls
    assert (("scheduler:recompute_events", 1, {"phase": "all"}), {}) in calls


def test_given_block_allocate_failed_return_when_hook_called_then_records_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    out = mh.block_allocate_failure_hooker(lambda *_a, **_k: None, object())

    assert out is None
    assert calls == [(("block_allocate_failures", 1, {"phase": "all"}), {})]


def test_given_block_allocate_false_return_when_hook_called_then_records_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    out = mh.block_allocate_failure_hooker(lambda *_a, **_k: False, object())

    assert out is False
    assert calls == [(("block_allocate_failures", 1, {"phase": "all"}), {})]


def test_given_block_allocate_exception_when_hook_called_then_records_and_reraises(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("allocator exploded")

    try:
        mh.block_allocate_failure_hooker(raise_error, object())
    except RuntimeError as exc:
        assert str(exc) == "allocator exploded"
    else:
        raise AssertionError("expected RuntimeError")

    assert calls == [(("block_allocate_failures", 1, {"phase": "all"}), {})]


def test_given_block_allocate_success_when_hook_called_then_does_not_record(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    out = mh.block_allocate_failure_hooker(lambda *_a, **_k: "allocated", object())

    assert out == "allocated"
    assert not calls


def test_given_rpc_timeout_when_hook_called_then_records_and_reraises(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    def raise_timeout(*_args, **_kwargs):
        raise TimeoutError("request timed out")

    try:
        mh.rpc_error_hooker(raise_timeout)
    except TimeoutError:
        pass
    else:
        raise AssertionError("expected TimeoutError")

    assert calls == [(("rpc_errors", 1, {"exception_type": "TimeoutError", "phase": "all"}), {})]


def test_given_rpc_connection_reset_when_hook_called_then_records_connection_reset(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    def raise_reset(*_args, **_kwargs):
        raise ConnectionError("connection reset by peer")

    try:
        mh.rpc_error_hooker(raise_reset)
    except ConnectionError:
        pass

    assert calls == [(("rpc_errors", 1, {"exception_type": "ConnectionError", "phase": "all"}), {})]


def test_given_rpc_runtime_error_when_hook_called_then_records_actual_exception_type(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    def raise_runtime_error(*_args, **_kwargs):
        raise RuntimeError("worker failed with error")

    try:
        mh.rpc_error_hooker(raise_runtime_error)
    except RuntimeError:
        pass

    assert calls == [(("rpc_errors", 1, {"exception_type": "RuntimeError", "phase": "all"}), {})]


def test_given_health_ok_when_hook_called_then_does_not_record(monkeypatch):
    calls = []
    response = SimpleNamespace(status_code=200)
    call_count = {"original": 0}
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    def original(*_args, **_kwargs):
        call_count["original"] += 1
        return response

    out = mh.health_check_failed_hooker(original, object())

    assert out is response
    assert call_count["original"] == 1
    assert not calls


def test_given_health_503_when_hook_called_then_records_failure(monkeypatch):
    calls = []
    response = SimpleNamespace(status_code=503)
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    out = mh.health_check_failed_hooker(lambda *_a, **_k: response, object())

    assert out is response
    assert calls == [((mh.HEALTH_CHECK_FAILED, 1, {"phase": "all"}), {})]


def test_given_async_health_503_when_hook_called_then_records_failure(monkeypatch):
    calls = []
    response = SimpleNamespace(status_code=503)
    call_count = {"original": 0}
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    async def original(*_args, **_kwargs):
        call_count["original"] += 1
        return response

    out = asyncio.run(mh.health_check_failed_hooker(original, object()))

    assert out is response
    assert call_count["original"] == 1
    assert calls == [((mh.HEALTH_CHECK_FAILED, 1, {"phase": "all"}), {})]


def test_given_health_engine_dead_error_when_hook_called_then_records_and_reraises(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    class EngineDeadError(Exception):
        pass

    def original(*_args, **_kwargs):
        raise EngineDeadError("dead")

    try:
        mh.health_check_failed_hooker(original, object())
    except EngineDeadError:
        pass
    else:
        raise AssertionError("expected EngineDeadError")

    assert calls == [((mh.HEALTH_CHECK_FAILED, 1, {"phase": "all"}), {})]


def test_given_health_metric_record_fails_when_hook_called_then_response_preserved(monkeypatch):
    response = SimpleNamespace(status_code=503)

    def record_metric(*_args, **_kwargs):
        raise RuntimeError("metrics down")

    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=record_metric))

    out = mh.health_check_failed_hooker(lambda *_a, **_k: response, object())

    assert out is response


def test_given_health_request_when_engine_client_wrapped_then_records_engine_dead_error(monkeypatch):
    calls = []
    request = SimpleNamespace(url=SimpleNamespace(path="/health"))
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    class EngineDeadError(Exception):
        pass

    class Client:
        async def check_health(self):
            raise EngineDeadError("dead")

    client = Client()
    out = mh.health_engine_client_hooker(lambda *_a, **_k: client, request)

    assert out is client
    try:
        asyncio.run(client.check_health())
    except EngineDeadError:
        pass
    else:
        raise AssertionError("expected EngineDeadError")

    assert calls == [((mh.HEALTH_CHECK_FAILED, 1, {"phase": "all"}), {})]


def test_given_eplb_do_update_when_worker_exposes_hotness_then_records_hotness_and_imbalance(monkeypatch):
    calls = []

    def record_metric(*args, **kwargs):
        if "labels" in kwargs:
            kwargs = {**kwargs, "labels": kwargs["labels"].copy()}
        calls.append((args, kwargs))

    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=record_metric))

    worker = SimpleNamespace(
        rank_id=0,
        latest_expert_hotness={
            "current_mean": 10,
            "current_max": 20,
            "update_mean": 8,
            "update_max": 12,
            "current_imbalance_list": [0.1, 0.2],
            "update_imbalance_list": [0.03, 0.04],
        },
    )

    def do_update(this):
        assert this is worker
        return "update_info"

    assert mh.eplb_do_update_hotness_handler(do_update, worker) == "update_info"

    metric_names = [args[0] for args, _kwargs in calls]
    assert "eplb:expert_hotness:current_mean" in metric_names
    assert "eplb:expert_hotness:current_max" in metric_names
    assert "eplb:expert_hotness:update_mean" in metric_names
    assert "eplb:expert_hotness:update_max" in metric_names
    summary_calls = [kwargs for args, kwargs in calls if args[0] == "eplb:expert_hotness:current_mean"]
    assert summary_calls[0]["labels"] == {"rank": "0", "phase": "all"}

    imbalance_calls = [kwargs for args, kwargs in calls if args[0] == "eplb:expert_hotness:imbalance"]
    assert len(imbalance_calls) == 4
    assert imbalance_calls[0]["labels"] == {"rank": "0", "phase": "current", "layer": "0"}
    assert imbalance_calls[-1]["labels"] == {"rank": "0", "phase": "update", "layer": "1"}


def test_given_eplb_nonzero_rank_when_handler_finishes_then_skips_metrics(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))

    worker = SimpleNamespace(rank_id=1, latest_expert_hotness={"current_mean": 10})
    assert mh.eplb_do_update_hotness_handler(lambda _self: "update_info", worker) == "update_info"

    assert not calls


def test_given_engine_memory_handler_when_compile_finishes_then_records_raw_metrics(monkeypatch):
    calls = []
    registered = []

    def record_metric(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=record_metric,
            get_or_create_metric=lambda *a, **k: registered.append((a, k)),
        ),
    )

    handler = mh.engine_memory_phase_handler(
        [
            {"name": "engine:memory:total_gb", "type": "gauge"},
            {"name": "engine:memory:utilization_ratio", "type": "gauge"},
            {"name": "engine:memory:reserved_gb", "type": "gauge"},
            {"name": "engine:memory:weights_gb", "type": "gauge"},
            {"name": "engine:memory:kvcache_gb", "type": "gauge"},
            {"name": "engine:memory:non_torch_gb", "type": "gauge"},
            {"name": "engine:memory:activation_gb", "type": "gauge"},
            {"name": "engine:memory:graph_gb", "type": "gauge"},
        ]
    )

    gib = 1024**3
    worker = SimpleNamespace(
        init_snapshot=SimpleNamespace(total_memory=32 * gib),
        cache_config=SimpleNamespace(gpu_memory_utilization=0.8),
        requested_memory=int(25.6 * gib),
        model_runner=SimpleNamespace(model_memory_usage=int(12.5 * gib)),
        available_kv_cache_memory_bytes=int(8.25 * gib),
        non_torch_memory=int(1.75 * gib),
        peak_activation_memory=int(2.5 * gib),
        npugraph_memory_bytes=int(0.5 * gib),
    )

    result = handler(lambda _self: "ok", worker)

    assert result == "ok"
    assert len(registered) == 8
    assert all(kwargs == {"metric_type": mh.MetricType.GAUGE} for _args, kwargs in registered)
    values = {args[0]: args[1] for args, _kwargs in calls}
    assert values["engine:memory:total_gb"] == 32.0
    assert values["engine:memory:utilization_ratio"] == 0.8
    assert values["engine:memory:reserved_gb"] == round(int(25.6 * gib) / gib, 2)
    assert values["engine:memory:weights_gb"] == round(int(12.5 * gib) / gib, 2)
    assert values["engine:memory:kvcache_gb"] == round(int(8.25 * gib) / gib, 2)
    assert values["engine:memory:non_torch_gb"] == round(int(1.75 * gib) / gib, 2)
    assert values["engine:memory:activation_gb"] == round(int(2.5 * gib) / gib, 2)
    assert values["engine:memory:graph_gb"] == round(int(0.5 * gib) / gib, 2)


def test_given_engine_memory_handler_when_attribute_missing_then_does_not_raise(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=lambda *a, **k: calls.append((a, k)),
            get_or_create_metric=lambda *a, **k: None,
        ),
    )

    handler = mh.engine_memory_phase_handler([{"name": "engine:memory:total_gb", "type": "gauge"}])

    worker = SimpleNamespace()

    result = handler(lambda _self: "ok", worker)

    assert result == "ok"


def test_given_engine_memory_handler_when_metric_config_object_then_registers_without_subscript(monkeypatch):
    calls = []
    registered = []
    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=lambda *a, **k: calls.append((a, k)),
            get_or_create_metric=lambda *a, **k: registered.append((a, k)),
        ),
    )

    handler = mh.engine_memory_phase_handler([MetricConfig(name="engine:memory:total_gb", type=MetricType.GAUGE)])
    worker = SimpleNamespace(init_snapshot=SimpleNamespace(total_memory=16 * 1024**3))

    result = handler(lambda _self: "ok", worker)

    assert result == "ok"
    assert registered == [(("engine:memory:total_gb",), {"metric_type": mh.MetricType.GAUGE})]
    assert calls == [(("engine:memory:total_gb", 16.0, {"phase": "all"}), {})]


def test_given_runtime_memory_handler_when_worker_executes_then_records_torch_memory(monkeypatch):
    calls = []
    registered = []
    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=lambda *a, **k: calls.append((a, k)),
            get_or_create_metric=lambda *a, **k: registered.append((a, k)),
        ),
    )

    handler = mh.runtime_memory_phase_handler(
        [
            {"name": "engine:memory:torch_reserved_gb", "type": "gauge"},
            {"name": "engine:memory:torch_allocated_gb", "type": "gauge"},
        ]
    )
    gib = 1024**3
    worker = SimpleNamespace(torch_reserved=int(18.25 * gib), torch_allocated=int(11.5 * gib))

    result = handler(lambda _self: "ok", worker)

    assert result == "ok"
    assert len(registered) == 2
    assert all(kwargs == {"metric_type": mh.MetricType.GAUGE} for _args, kwargs in registered)
    values = {args[0]: args[1] for args, _kwargs in calls}
    assert values["engine:memory:torch_reserved_gb"] == round(int(18.25 * gib) / gib, 2)
    assert values["engine:memory:torch_allocated_gb"] == 11.5


def test_given_runtime_memory_handler_when_attribute_missing_then_does_not_raise(monkeypatch):
    calls = []
    monkeypatch.setattr(
        mh,
        "metrics_client",
        SimpleNamespace(
            record_metric=lambda *a, **k: calls.append((a, k)),
            get_or_create_metric=lambda *a, **k: None,
        ),
    )

    handler = mh.runtime_memory_phase_handler([{"name": "engine:memory:torch_reserved_gb", "type": "gauge"}])

    result = handler(lambda _self: "ok", SimpleNamespace())

    assert result == "ok"
    assert not calls


def test_given_format_gib_value_when_zero_then_returns_zero():
    assert mh._format_gib_value(0) == 0.0


def test_given_format_gib_value_when_int_input_then_returns_correct_value():
    gib = 1024**3
    assert mh._format_gib_value(25 * gib) == 25.0


def test_given_format_gib_value_when_very_large_then_returns_rounded():
    gib = 1024**3
    result = mh._format_gib_value(1024 * gib)
    assert result == 1024.0
