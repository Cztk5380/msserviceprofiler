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

import sys
import os
import threading
import contextlib
from collections import namedtuple
from unittest.mock import patch, MagicMock, call
import pytest

from ms_service_profiler.patcher.vllm.handlers.v1 import model_handlers
from ms_service_profiler.patcher.vllm.handlers.v1.utils import create_state_getter

from .fake_ms_service_profiler import Profiler, Level


# Reset profiler and state before each test
@pytest.fixture(autouse=True)
def reset_state():
    # 重置状态获取器，以清空内部的线程本地状态
    model_handlers._get_state = create_state_getter(model_handlers.HookState)
    Profiler.reset()
    yield


# Test helpers
SchedulerOutput = namedtuple(
    "SchedulerOutput",
    [
        "scheduled_new_reqs",
        "scheduled_cached_reqs",
        "num_scheduled_tokens",
        "finished_req_ids",
        "total_num_scheduled_tokens",
    ],
)
Request = namedtuple("Request", ["req_id", "prompt_token_ids", "num_computed_tokens"])


def create_request(request_id, token_count=10, computed_tokens=0):
    return Request(req_id=request_id, prompt_token_ids=[0] * token_count, num_computed_tokens=computed_tokens)


def test_get_state_given_first_call_when_no_existing_state_then_create_new_state():
    # 重新绑定获取器，确保是“第一次”获取
    model_handlers._get_state = create_state_getter(model_handlers.HookState)
    state = model_handlers._get_state()
    assert isinstance(state, model_handlers.HookState)
    # 再次获取应返回同一实例
    assert model_handlers._get_state() is state


def test_get_state_given_existing_state_when_called_then_return_same_instance():
    # 首次获取并保存
    state1 = model_handlers._get_state()
    # 再次获取应返回相同实例
    assert model_handlers._get_state() is state1


def test_compute_logits_given_valid_input_when_called_then_profile_span():
    mock_original = MagicMock(return_value="logits")
    mock_this = MagicMock()

    result = model_handlers.compute_logits(mock_original, mock_this, "input_ids", "scores")

    mock_original.assert_called_with(mock_this, "input_ids", "scores")
    assert result == "logits"
    assert len(Profiler.instance_calls) == 1
    calls = Profiler.instance_calls[0]
    assert ("span_start", "computing_logits") in calls
    assert "span_end" in calls


def test_sampler_forward_given_valid_input_when_called_then_profile_span():
    mock_original = MagicMock(return_value="samples")
    mock_this = MagicMock()

    result = model_handlers.sampler_forward(mock_original, mock_this, "input_ids")

    mock_original.assert_called_with(mock_this, "input_ids")
    assert result == "samples"
    assert len(Profiler.instance_calls) == 1
    calls = Profiler.instance_calls[0]
    assert ("span_start", "sample") in calls
    assert "span_end" in calls


def test_execute_model_given_new_requests_when_processing_then_update_state_and_profile():
    state = model_handlers.HookState()
    req1 = create_request("req1", token_count=5)
    req2 = create_request("req2", token_count=3)

    scheduler_output = SchedulerOutput(
        scheduled_new_reqs=[req1, req2],
        scheduled_cached_reqs=[],
        num_scheduled_tokens={"req1": 5, "req2": 3},
        finished_req_ids=[],
        total_num_scheduled_tokens=8,
    )

    mock_original = MagicMock(return_value="output")

    with patch.object(model_handlers, "_get_state", return_value=state):
        result = model_handlers.execute_model(mock_original, MagicMock(), scheduler_output)

    assert result == "output"
    assert state.request_id_to_prompt_token_len == {"req1": 5, "req2": 3}

    # Verify profiling calls
    assert len(Profiler.instance_calls) == 2  # One for batch, one for forward

    # Check batch profiling
    batch_calls = Profiler.instance_calls[0]
    # 允许实现附带额外字段（如 type），仅校验 rid 与 iter
    res_entry = next(x for x in batch_calls if isinstance(x, tuple) and x[0] == "res")
    res_payload = res_entry[1]
    assert [{"rid": d["rid"], "iter": d["iter"]} for d in res_payload] == [
        {"rid": "req1", "iter": 0},
        {"rid": "req2", "iter": 0},
    ]
    assert ("attr", "batch_type", "Prefill") in batch_calls
    assert ("attr", "batch_size", 8) in batch_calls
    assert ("span_start", "modelExec") in batch_calls

    # Check forward profiler setup
    assert state.forward_profiler is not None


def test_execute_model_given_prefill_batch_when_processing_then_set_prefill_flag():
    state = model_handlers.HookState()
    state.request_id_to_prompt_token_len = {"req1": 5, "req2": 10}
    req1 = create_request("req1", token_count=10, computed_tokens=5)  # Partial processing
    req2 = create_request("req2", token_count=5, computed_tokens=5)  # Completed

    scheduler_output = SchedulerOutput(
        scheduled_new_reqs=[],
        scheduled_cached_reqs=[req1, req2],
        num_scheduled_tokens={"req1": 5, "req2": 3},
        finished_req_ids=[],
        total_num_scheduled_tokens=8,
    )

    mock_original = MagicMock()

    with patch.object(model_handlers, "_get_state", return_value=state):
        model_handlers.execute_model(mock_original, MagicMock(), scheduler_output)

    # 包含一个 Prefill 与一个 Decode，当前实现返回 "Prefill,Decode"
    batch_calls = Profiler.instance_calls[0]
    assert ("attr", "batch_type", "Prefill,Decode") in batch_calls


def test_execute_model_given_decode_batch_when_processing_then_set_decode_flag():
    state = model_handlers.HookState()
    req1 = create_request("req1", token_count=10, computed_tokens=10)  # Completed
    req2 = create_request("req2", token_count=5, computed_tokens=5)  # Completed

    scheduler_output = SchedulerOutput(
        scheduled_new_reqs=[],
        scheduled_cached_reqs=[req1, req2],
        num_scheduled_tokens={"req1": 5, "req2": 3},
        finished_req_ids=[],
        total_num_scheduled_tokens=8,
    )

    mock_original = MagicMock()

    with patch.object(model_handlers, "_get_state", return_value=state):
        model_handlers.execute_model(mock_original, MagicMock(), scheduler_output)

    # Should detect decode because all requests have computed tokens >= prompt length
    batch_calls = Profiler.instance_calls[0]
    assert ("attr", "batch_type", "Decode") in batch_calls


def test_execute_model_given_no_requests_when_processing_then_no_profiling():
    state = model_handlers.HookState()
    scheduler_output = SchedulerOutput(
        scheduled_new_reqs=[],
        scheduled_cached_reqs=[],
        num_scheduled_tokens={},
        finished_req_ids=[],
        total_num_scheduled_tokens=0,
    )

    mock_original = MagicMock(return_value="output")

    with patch.object(model_handlers, "_get_state", return_value=state):
        result = model_handlers.execute_model(mock_original, MagicMock(), scheduler_output)

    assert result == "output"
    assert len(Profiler.instance_calls) == 0
    assert state.forward_profiler is None


def test_set_forward_context_given_no_forward_profiler_when_used_then_create_new_profiler():
    state = model_handlers.HookState()
    mock_original = MagicMock()

    with patch.object(model_handlers, "_get_state", return_value=state):
        with model_handlers.set_forward_context(mock_original):
            pass

    assert len(Profiler.instance_calls) == 1
    calls = Profiler.instance_calls[0]
    assert ("span_start", "set_forward_context") in calls
    assert "span_end" in calls
    assert state.forward_profiler is None


def test_set_forward_context_given_existing_forward_profiler_when_used_then_reuse_profiler():
    state = model_handlers.HookState()
    state.forward_profiler = Profiler(Level.INFO)
    mock_original = MagicMock()

    with patch.object(model_handlers, "_get_state", return_value=state):
        with model_handlers.set_forward_context(mock_original):
            pass

    # Should use existing profiler instead of creating new one
    assert len(Profiler.instance_calls) > 0
    assert state.forward_profiler is None  # Should be cleared after use


def test_set_forward_context_given_context_manager_when_used_then_call_original():
    mock_original = MagicMock()
    mock_context = MagicMock()
    mock_original.return_value = mock_context

    with patch.object(model_handlers, "_get_state", return_value=model_handlers.HookState()):
        with model_handlers.set_forward_context(mock_original):
            pass

    mock_original.assert_called_once()
    mock_context.__enter__.assert_called_once()
    mock_context.__exit__.assert_called_once()


def test_hook_state_initialization():
    state = model_handlers.HookState()
    assert state.forward_profiler is None
    assert state.execute_model_first_run is True
    assert state.begin_forward_first_run is True
    assert not state.request_id_to_prompt_token_len
    assert not state.request_id_to_iter
    assert state.request_id_list == []
    assert state.mtp_num_accepted_by_req == {}
    assert state.mtp_num_draft_by_req == {}


def test_hook_state_clear_mtp():
    state = model_handlers.HookState()
    state.mtp_num_accepted_by_req = {"r1": 2}
    state.mtp_num_draft_by_req = {"r1": 3}
    state.clear_mtp()
    assert state.mtp_num_accepted_by_req == {}
    assert state.mtp_num_draft_by_req == {}


def test_normalize_req_id_dict_with_rid():
    assert model_handlers._normalize_req_id({"rid": "req_1"}) == "req_1"
    assert model_handlers._normalize_req_id({"rid": 123}) == 123


def test_normalize_req_id_dict_without_rid_or_rid_none():
    assert model_handlers._normalize_req_id({}) == {}
    assert model_handlers._normalize_req_id({"rid": None}) == {"rid": None}


def test_normalize_req_id_non_dict_returns_as_is():
    assert model_handlers._normalize_req_id("req_2") == "req_2"
    assert model_handlers._normalize_req_id(456) == 456


def test_execute_model_runner_given_no_request_id_list_when_called_then_no_profiling():
    state = model_handlers.HookState()
    state.request_id_to_prompt_token_len = {}
    state.request_id_to_iter = {}
    scheduler_output = SchedulerOutput(
        scheduled_new_reqs=[],
        scheduled_cached_reqs=[],
        num_scheduled_tokens={},
        finished_req_ids=[],
        total_num_scheduled_tokens=0,
    )
    mock_original = MagicMock(return_value="ret")
    with patch.object(model_handlers, "_get_state", return_value=state):
        result = model_handlers.execute_model_runner(mock_original, MagicMock(), scheduler_output)
    assert result == "ret"
    assert len(Profiler.instance_calls) == 0


def test_execute_model_runner_given_request_id_list_when_has_mtp_accepted_then_attr_and_clear_mtp():
    state = model_handlers.HookState()
    state.request_id_to_prompt_token_len = {"req_1": 5}
    state.request_id_to_iter = {}
    state.mtp_num_accepted_by_req = {"req_1": 2}
    scheduler_output = SchedulerOutput(
        scheduled_new_reqs=[create_request("req_1", token_count=5)],
        scheduled_cached_reqs=[],
        num_scheduled_tokens={"req_1": 5},
        finished_req_ids=[],
        total_num_scheduled_tokens=5,
    )
    mock_original = MagicMock(return_value=None)
    with patch.object(model_handlers, "_get_state", return_value=state):
        result = model_handlers.execute_model_runner(mock_original, MagicMock(), scheduler_output)
    assert result is None
    assert state.request_id_list
    all_calls = sum(Profiler.instance_calls, [])
    assert any(isinstance(c, tuple) and len(c) >= 3 and c[0] == "attr" and c[1] == "spec_decode_accepted_by_req"
               for c in all_calls)
    assert state.mtp_num_accepted_by_req == {}
    assert state.mtp_num_draft_by_req == {}


def test_execute_model_runner_given_no_mtp_accepted_uses_runner_output():
    state = model_handlers.HookState()
    state.request_id_to_prompt_token_len = {"r1": 5}
    state.request_id_to_iter = {}
    scheduler_output = SchedulerOutput(
        scheduled_new_reqs=[create_request("r1", token_count=5)],
        scheduled_cached_reqs=[],
        num_scheduled_tokens={"r1": 5},
        finished_req_ids=[],
        total_num_scheduled_tokens=5,
    )
    runner_ret = MagicMock()
    runner_ret.req_ids = ["r1"]
    runner_ret.sampled_token_ids = [[1, 2, 3]]
    mock_original = MagicMock(return_value=runner_ret)
    with patch.object(model_handlers, "_get_state", return_value=state):
        model_handlers.execute_model_runner(mock_original, MagicMock(), scheduler_output)
    all_calls = sum(Profiler.instance_calls, [])
    assert any(isinstance(c, tuple) and len(c) >= 3 and c[0] == "attr" and c[1] == "spec_decode_accepted_by_req"
               for c in all_calls)


def test_accepted_by_req_from_runner_output_none():
    assert model_handlers._accepted_by_req_from_runner_output(None) is None


def test_accepted_by_req_from_runner_output_with_sampled_token_ids_and_req_ids():
    ret = MagicMock()
    ret.req_ids = ["a", "b"]
    ret.sampled_token_ids = [[1, 2, 3], [1, 2]]
    out = model_handlers._accepted_by_req_from_runner_output(ret)
    assert out == {"a": 2, "b": 1}


def test_accepted_by_req_from_runner_output_ids_longer_than_tokens_caps():
    ret = MagicMock()
    ret.req_ids = ["a", "b", "c"]
    ret.sampled_token_ids = [[1, 2]]
    out = model_handlers._accepted_by_req_from_runner_output(ret)
    assert out == {"a": 1, "b": 0, "c": 0}


def test_accepted_by_req_from_runner_output_empty_tokens_zero():
    ret = MagicMock()
    ret.req_ids = ["a"]
    ret.sampled_token_ids = [[]]
    out = model_handlers._accepted_by_req_from_runner_output(ret)
    assert out == {"a": 0}


def test_accepted_by_req_from_runner_output_get_output_path():
    inner = MagicMock()
    inner.req_ids = ["x"]
    inner.sampled_token_ids = [[1, 2]]
    outer = type("Outer", (), {"get_output": MagicMock(return_value=inner)})()

    out = model_handlers._accepted_by_req_from_runner_output(outer)
    assert out == {"x": 1}


def test_accepted_by_req_from_runner_output_get_output_exception_returns_none():
    class OuterWithGetOutput:
        def get_output(self):
            raise RuntimeError()

    assert model_handlers._accepted_by_req_from_runner_output(OuterWithGetOutput()) is None


def test_capture_async_given_forward_tag_when_used_then_prof_res_request_id_list():
    state = model_handlers.HookState()
    state.request_id_list = ["r1", "r2"]
    mock_original = MagicMock()
    mock_original.return_value.__enter__ = MagicMock(return_value=None)
    mock_original.return_value.__exit__ = MagicMock(return_value=None)
    with patch.object(model_handlers, "_get_state", return_value=state):
        with model_handlers.capture_async(mock_original, MagicMock(), "forward"):
            pass
    all_calls = sum(Profiler.instance_calls, [])
    assert any(isinstance(c, tuple) and c[0] == "res" and c[1] == ["r1", "r2"] for c in all_calls)


def test_capture_async_given_non_forward_tag_when_used_then_span_only():
    mock_original = MagicMock()
    mock_original.return_value.__enter__ = MagicMock(return_value=None)
    mock_original.return_value.__exit__ = MagicMock(return_value=None)
    with patch.object(model_handlers, "_get_state", return_value=MagicMock(request_id_list=[])):
        with model_handlers.capture_async(mock_original, MagicMock(), "backward"):
            pass
    assert len(Profiler.instance_calls) >= 1
    calls = Profiler.instance_calls[0]
    assert ("span_start", "backward") in calls
