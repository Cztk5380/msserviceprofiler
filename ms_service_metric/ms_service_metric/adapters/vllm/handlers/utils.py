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
"""Shared helpers for vLLM metric handlers."""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, Generator, Iterable, Iterator, Tuple

from ms_service_metric.utils.logger import get_logger


logger = get_logger(__name__)

QUEUE_PHASES = ("prefill", "decode", "unknown")


class SchedulerPhaseState:
    """Track prompt lengths across scheduler iterations for real P/D splitting."""

    def __init__(self):
        self.request_id_to_prompt_token_len: Dict[str, int] = {}
        self.pid = os.getpid()


_scheduler_phase_state = threading.local()


def get_scheduler_phase_state() -> SchedulerPhaseState:
    state = getattr(_scheduler_phase_state, "state", None)
    if state is None or getattr(state, "pid", None) != os.getpid():
        _scheduler_phase_state.state = SchedulerPhaseState()
    return _scheduler_phase_state.state


def clear_request_phase_state(state: SchedulerPhaseState, *requests: Any) -> None:
    for req in requests:
        req_id = _extract_req_id(req)
        if req_id is not None:
            state.request_id_to_prompt_token_len.pop(req_id, None)


def _iter_cached_req_id_and_num_comp(cached) -> Generator[Tuple[str, int], None, None]:
    if cached is None:
        return
    req_ids = getattr(cached, "req_ids", None)
    if req_ids is not None:
        for rid, num_comp in zip(cached.req_ids, cached.num_computed_tokens):
            yield rid, num_comp
        return
    try:
        for item in cached:
            rid = getattr(item, "req_id", None)
            num_comp = getattr(item, "num_computed_tokens", None)
            if rid is not None and num_comp is not None:
                yield rid, num_comp
    except TypeError:
        return


def _iter_new_req_id_and_num_comp(new_reqs) -> Generator[Tuple[str, int], None, None]:
    for item in new_reqs or []:
        rid = getattr(item, "req_id", None)
        num_comp = getattr(item, "num_computed_tokens", None)
        if rid is not None and num_comp is not None:
            yield rid, num_comp


def _iter_scheduled_tokens(scheduled_tokens_by_rid: Any) -> Iterator[Tuple[str | None, int | float]]:
    if hasattr(scheduled_tokens_by_rid, "items"):
        yield from scheduled_tokens_by_rid.items()
        return

    if not scheduled_tokens_by_rid:
        return

    try:
        iterator = iter(scheduled_tokens_by_rid)
    except TypeError:
        logger.warning("Unexpected num_scheduled_tokens type: %s", type(scheduled_tokens_by_rid).__name__)
        return

    logger.warning("num_scheduled_tokens has no request ids, recording scheduled tokens as unknown phase")
    for num_scheduled_tokens in iterator:
        if isinstance(num_scheduled_tokens, (int, float)):
            yield None, num_scheduled_tokens


def classify_phase_from_lengths(prompt_len: int | None, num_computed_tokens: int | None) -> str:
    if prompt_len is None or num_computed_tokens is None:
        return "unknown"
    return "prefill" if num_computed_tokens < prompt_len else "decode"


def _iter_req_candidates(req: Any) -> Iterable[Any]:
    yield req
    nested_request = getattr(req, "request", None)
    if nested_request is not None:
        yield nested_request
    nested_state = getattr(req, "request_state", None)
    if nested_state is not None:
        yield nested_state


def _extract_req_id(req: Any) -> str | None:
    for obj in _iter_req_candidates(req):
        rid = getattr(obj, "request_id", None)
        if rid is not None:
            return rid
        rid = getattr(obj, "req_id", None)
        if rid is not None:
            return rid
    return None


def _extract_prompt_len(req: Any, state: SchedulerPhaseState) -> int | None:
    for obj in _iter_req_candidates(req):
        num_prompt_tokens = getattr(obj, "num_prompt_tokens", None)
        if num_prompt_tokens is not None:
            return num_prompt_tokens
        prompt_token_ids = getattr(obj, "prompt_token_ids", None)
        if prompt_token_ids is not None:
            return len(prompt_token_ids)

    req_id = _extract_req_id(req)
    if req_id is not None:
        return state.request_id_to_prompt_token_len.get(req_id)
    return None


def _extract_num_computed_tokens(req: Any) -> int | None:
    for obj in _iter_req_candidates(req):
        num_comp = getattr(obj, "num_computed_tokens", None)
        if num_comp is not None:
            return num_comp
    return None


def collect_queue_phase_metrics(
    state: SchedulerPhaseState,
    requests: Iterable[Any] | None,
) -> Dict[str, int]:
    phase_counts = {phase: 0 for phase in QUEUE_PHASES}
    if requests is None:
        logger.debug("Queue phase metrics skipped because request queue is missing")
        return phase_counts

    for req in requests:
        req_id = _extract_req_id(req)
        prompt_len = _extract_prompt_len(req, state)
        num_comp = _extract_num_computed_tokens(req)

        if req_id is not None and prompt_len is not None:
            state.request_id_to_prompt_token_len[req_id] = prompt_len

        phase = classify_phase_from_lengths(prompt_len, num_comp)
        phase_counts[phase] += 1

    return phase_counts


def collect_phase_metrics(state: SchedulerPhaseState, scheduler_output: Any) -> Dict[str, Dict[str, float]]:
    """Split one scheduled batch into Prefill/Decode request groups."""
    for new_req in getattr(scheduler_output, "scheduled_new_reqs", []) or []:
        req_id = getattr(new_req, "req_id", None)
        prompt_token_ids = getattr(new_req, "prompt_token_ids", None)
        if req_id is not None and prompt_token_ids is not None:
            state.request_id_to_prompt_token_len[req_id] = len(prompt_token_ids)

    num_comp_by_rid: Dict[str, int] = {}
    for rid, num_comp in _iter_cached_req_id_and_num_comp(getattr(scheduler_output, "scheduled_cached_reqs", None)):
        num_comp_by_rid[rid] = num_comp
    for rid, num_comp in _iter_new_req_id_and_num_comp(getattr(scheduler_output, "scheduled_new_reqs", None)):
        num_comp_by_rid[rid] = num_comp

    phase_stats: Dict[str, Dict[str, float]] = {
        phase: {"batch_size": 0, "scheduled_tokens_sum": 0}
        for phase in QUEUE_PHASES
    }

    scheduled_tokens_by_rid = getattr(scheduler_output, "num_scheduled_tokens", {})
    for request_id, num_scheduled_tokens in _iter_scheduled_tokens(scheduled_tokens_by_rid):
        prompt_len = state.request_id_to_prompt_token_len.get(request_id) if request_id is not None else None
        num_comp = num_comp_by_rid.get(request_id) if request_id is not None else None
        phase = classify_phase_from_lengths(prompt_len, num_comp)
        source = "new_or_cached" if request_id in num_comp_by_rid else "scheduled_only"
        logger.debug(
            "Phase split rid=%s phase=%s prompt_len=%s num_comp=%s scheduled_tokens=%s source=%s",
            request_id,
            phase,
            prompt_len,
            num_comp,
            num_scheduled_tokens,
            source,
        )
        phase_stats[phase]["batch_size"] += 1
        phase_stats[phase]["scheduled_tokens_sum"] += num_scheduled_tokens

    for phase_values in phase_stats.values():
        batch_size = phase_values["batch_size"]
        phase_values["scheduled_tokens_avg"] = (
            phase_values["scheduled_tokens_sum"] / batch_size if batch_size > 0 else 0
        )

    for finished_req_id in getattr(scheduler_output, "finished_req_ids", []) or []:
        state.request_id_to_prompt_token_len.pop(finished_req_id, None)

    return phase_stats
