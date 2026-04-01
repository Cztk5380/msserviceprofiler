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

import ms_service_metric.adapters.vllm.handlers.metric_handlers as mh


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


def test_given_timing_context_normal_exit_when_exit_then_records_metric_and_timeline(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    tr_calls = []
    monkeypatch.setattr(mh, "timeline_recorder", SimpleNamespace(record=lambda *a, **k: tr_calls.append((a, k))))
    # __enter__ takes start time, __exit__ takes end time — fixed sequence, no coupling to record_metric calls.
    times = iter([100.0, 101.5])
    monkeypatch.setattr(mh.time, "time", lambda: next(times))

    class _Ctx:
        def __enter__(self):
            return "ctx"

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    tcm = mh.TimingContextManager("abc", _Ctx())
    assert tcm.__enter__() == "ctx"
    tcm.__exit__(None, None, None)
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

    tcm = mh.TimingContextManager("abc", _Ctx())
    tcm.__enter__()
    tcm.__exit__(RuntimeError, RuntimeError("x"), None)
    assert calls == []


def test_given_original_context_factory_when_hook_wrapped_then_returns_timing_context():
    out = mh.record_function_timer_hook(lambda name, *a, **k: SimpleNamespace(__enter__=lambda: None, __exit__=lambda *_: False), "n")
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
    times = iter([10.0, 10.4])
    monkeypatch.setattr(mh.time, "time", lambda: next(times))

    out = mh.runner_get_output_hooker(lambda *_a, **_k: 123)
    assert out == 123
    assert len(calls) == 1
    assert len(tr_calls) == 1


def test_given_scheduler_result_when_scheduler_hook_called_then_records_core_metrics(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    times = iter([1.0, 1.2])
    monkeypatch.setattr(mh.time, "time", lambda: next(times))

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


def test_given_scheduler_result_without_tokens_when_scheduler_hook_called_then_avg_sum_not_recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(mh, "metrics_client", SimpleNamespace(record_metric=lambda *a, **k: calls.append((a, k))))
    times = iter([2.0, 2.1])
    monkeypatch.setattr(mh.time, "time", lambda: next(times))

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
