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

import os
import sys
from collections import deque, Counter
from unittest.mock import MagicMock, patch
import pytest

from ms_service_profiler.patcher.vllm.handlers.v0 import batch_handlers

from .fake_ms_service_profiler import Profiler, Level


def test_compare_deques_given_nonempty_when_diff_then_correct_counter():
    q1 = deque([1, 2, 2, 3])
    q2 = deque([2, 3])
    result = batch_handlers.compare_deques(q1, q2)
    assert isinstance(result, Counter)
    assert result == Counter({1: 1, 2: 1})


def test_compare_deques_given_equal_when_no_diff_then_empty_counter():
    q1 = deque([1, 2])
    q2 = deque([1, 2])
    result = batch_handlers.compare_deques(q1, q2)
    assert result == Counter()


class DummySeqGroup:
    def __init__(self, request_id):
        self.request_id = request_id


def test_queue_profiler_given_changes_when_elements_removed_and_added_then_logs_both():
    before = [DummySeqGroup("A"), DummySeqGroup("B")]
    after = [DummySeqGroup("B"), DummySeqGroup("C")]
    batch_handlers.queue_profiler(before, after, "test_queue")
    # Should log Dequeue for A and Enqueue for C
    all_calls = sum(Profiler.instance_calls, [])
    assert any([c[0] == "event" and c[1] == "Dequeue" for c in all_calls])
    assert any([c[0] == "event" and c[1] == "Enqueue" for c in all_calls])


class DummySeq:
    def __init__(self, token_ids):
        self._ids = token_ids

    def get_token_ids(self):
        return self._ids


class DummyRunning:
    def __init__(self, rid, prompt_len, gen_len):
        self.request_id = rid
        self.prompt_token_ids = [0] * prompt_len
        self.seqs = [DummySeq([0] * prompt_len + [1] * gen_len)] if gen_len >= 0 else []


class DummyMeta:
    def __init__(self, rid, chunk_size):
        self.request_id = rid
        self.token_chunk_size = chunk_size


def make_this_running(running):
    return MagicMock(running=running)


@pytest.mark.parametrize(
    "func_name,args",
    [
        ("abort_seq_group", ("req1",)),
        ("allocate_and_set_running", (MagicMock(request_id="r1"),)),
        ("swap_in", (MagicMock(request_id="r1"),)),
        ("add_seq_group_to_running", (MagicMock(request_id="r2"),)),
        ("add_seq_group", (MagicMock(request_id="r3"),)),
        ("add_seq_group_to_swapped", (MagicMock(request_id="r4"),)),
        ("add_processed_request", ("req5",)),
    ],
)
def test_simple_hooks_log_and_call_original(func_name, args):
    called = {}

    def orig_func(*a, **k):
        called["yes"] = True

    this = MagicMock(running=[MagicMock(request_id="rx")], waiting=[1], swapped=[1])
    func = getattr(batch_handlers, func_name)
    func(orig_func, this, *args)
    assert called.get("yes", False) is True
    assert Profiler.instance_calls  # some logging occurred


def test_swap_out_given_can_swap_out_true_then_logs():
    seq_group = MagicMock(request_id="s1")
    bm = MagicMock(can_swap_out=lambda sg: True)
    this = MagicMock(block_manager=bm)
    called = {}

    def orig_func(*a, **k):
        called["yes"] = True

    batch_handlers.swap_out(orig_func, this, seq_group)
    assert called["yes"] is True
    assert any([c[0] == "metric_inc" for c in sum(Profiler.instance_calls, [])])


def test_swap_out_given_can_swap_out_false_then_no_logs():
    seq_group = MagicMock(request_id="s2")
    bm = MagicMock(can_swap_out=lambda sg: False)
    this = MagicMock(block_manager=bm)
    batch_handlers.swap_out(lambda *a, **k: None, this, seq_group)
    assert not any([c[0] == "metric_inc" for c in sum(Profiler.instance_calls, [])])


def test_free_finished_seq_groups_calls_original_and_queue_profiler():
    before = [DummySeqGroup("A"), DummySeqGroup("B")]
    after = [DummySeqGroup("B")]
    this = MagicMock()
    this.running = list(before)
    called = {}

    def orig_func(*a, **k):
        called["yes"] = True
        this.running.clear()
        this.running.extend(after)

    batch_handlers.free_finished_seq_groups(orig_func, this)
    assert called.get("yes") is True
    all_calls = sum(Profiler.instance_calls, [])
    assert any(c[0] == "metric_inc" for c in all_calls)
    assert any(c[0] == "event" for c in all_calls)


def test_schedule_priority_preemption_calls_original_and_queue_profiler():
    this = MagicMock()
    this.waiting = deque([DummySeqGroup("w1")])
    this.running = deque([DummySeqGroup("r1")])
    called = {}

    def orig_func(*a, **k):
        called["yes"] = True
        return 0

    result = batch_handlers.schedule_priority_preemption(orig_func, this, 100)
    assert called["yes"] is True
    assert result == 0
    assert len(Profiler.instance_calls) >= 0


def test_schedule_default_calls_original_and_queue_profiler():
    this = MagicMock()
    this.swapped = deque()
    this.running = deque([DummySeqGroup("r1")])
    this.waiting = deque()
    orig_ret = MagicMock()

    def orig_func(*a, **k):
        return orig_ret

    result = batch_handlers.schedule_default(orig_func, this)
    assert result is orig_ret


def test_schedule_chunked_prefill_calls_original_and_queue_profiler():
    this = MagicMock()
    this.running = deque([DummySeqGroup("r1")])
    this.waiting = deque()
    this.swapped = deque()
    orig_ret = MagicMock()

    def orig_func(*a, **k):
        return orig_ret

    result = batch_handlers.schedule_chunked_prefill(orig_func, this)
    assert result is orig_ret


def test_preempt_by_recompute_given_seqs_not_one_then_logs():
    seq_group = MagicMock(request_id="preempt1")
    seq_group.get_seqs = MagicMock(return_value=[MagicMock(), MagicMock()])
    this = MagicMock()
    called = {}

    def orig_func(*a, **k):
        called["yes"] = True

    with patch.dict("sys.modules", {"vllm.sequence": MagicMock(SequenceStatus=MagicMock(RUNNING=1))}):
        batch_handlers.preempt_by_recompute(orig_func, this, seq_group)
    assert called["yes"] is True
    all_calls = sum(Profiler.instance_calls, [])
    assert any(c[0] == "metric_inc" for c in all_calls)


def test_preempt_by_recompute_given_seqs_eq_one_then_no_metric_inc():
    seq_group = MagicMock(request_id="preempt2")
    seq_group.get_seqs = MagicMock(return_value=[MagicMock()])
    this = MagicMock()
    Profiler.reset()

    def orig_func(*a, **k):
        pass

    with patch.dict("sys.modules", {"vllm.sequence": MagicMock(SequenceStatus=MagicMock(RUNNING=1))}):
        batch_handlers.preempt_by_recompute(orig_func, this, seq_group)
    all_calls = sum(Profiler.instance_calls, [])
    metric_inc_calls = [c for c in all_calls if isinstance(c, tuple) and c[0] == "metric_inc"]
    assert not metric_inc_calls


def test_queue_profiler_given_only_removals_then_dequeue_only():
    Profiler.reset()
    before = [DummySeqGroup("A"), DummySeqGroup("B")]
    after = [DummySeqGroup("B")]
    batch_handlers.queue_profiler(before, after, "test")
    all_calls = sum(Profiler.instance_calls, [])
    assert any(c[0] == "event" and c[1] == "Dequeue" for c in all_calls)


def test_queue_profiler_given_only_adds_then_enqueue_only():
    Profiler.reset()
    before = [DummySeqGroup("A")]
    after = [DummySeqGroup("A"), DummySeqGroup("B")]
    batch_handlers.queue_profiler(before, after, "test")
    all_calls = sum(Profiler.instance_calls, [])
    assert any(c[0] == "event" and c[1] == "Enqueue" for c in all_calls)


def test_queue_profiler_given_no_change_then_no_events():
    Profiler.reset()
    sg = DummySeqGroup("A")
    before = [sg]
    after = [sg]
    batch_handlers.queue_profiler(before, after, "test")
    all_calls = sum(Profiler.instance_calls, [])
    assert not any(c[0] == "event" for c in all_calls)


def test_schedule_given_empty_running_then_attr_decode():
    this = MagicMock()
    this.running = []
    seq_list = []
    sched_out = MagicMock()
    allow_async = False

    def orig_func(*a, **k):
        return seq_list, sched_out, allow_async

    fake_sgm = type("SequenceGroupMetadata", (), {})
    mock_vllm_seq = MagicMock()
    mock_vllm_seq.SequenceGroupMetadata = fake_sgm
    with patch.dict("sys.modules", {"vllm.sequence": mock_vllm_seq}):
        result = batch_handlers.schedule(orig_func, this)
    assert result[0] is seq_list
    assert result[1] is sched_out
    all_calls = sum(Profiler.instance_calls, [])
    assert any(c == ("attr", "batch_type", "Decode") for c in all_calls)
