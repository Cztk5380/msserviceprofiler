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
from collections import namedtuple
from unittest.mock import patch, MagicMock, call
import pytest

from ms_service_profiler.vllm_profiler.vllm_v1 import kvcache_hookers

from .fake_ms_service_profiler import Profiler, Level


Request = namedtuple("Request", ["request_id", "num_tokens"])


def test_free_given_valid_request_when_called_then_log_free():
    mock_this = MagicMock()
    mock_this.block_pool.get_num_free_blocks.return_value = 50
    request = Request(request_id="req2", num_tokens=5)
    mock_original = MagicMock(return_value="result")

    result = kvcache_hookers.free(mock_original, mock_this, request)

    mock_original.assert_called_with(mock_this, request)
    assert result == "result"
    assert len(Profiler.instance_calls) == 1
    calls = Profiler.instance_calls[0]
    assert ("res", "req2") in calls
    assert ("metric", "deviceBlock", 50) in calls
    assert ("event", "Free") in calls


def test_get_computed_blocks_given_cache_hit_when_condition_met_then_log_hit_rate():
    mock_this = MagicMock()
    request = Request(request_id="req3", num_tokens=10)
    mock_original = MagicMock(return_value=(["block1", "block2"], 8))  # (blocks, num_new_computed_tokens)

    result = kvcache_hookers.get_computed_blocks(mock_original, mock_this, request)

    mock_original.assert_called_with(mock_this, request)
    assert result == (["block1", "block2"], 8)
    assert len(Profiler.instance_calls) == 1
    calls = Profiler.instance_calls[0]
    assert ("res", "req3") in calls
    assert ("attr", "hitCache", 0.8) in calls  # 8/10 = 0.8
    assert ("event", "CacheHitRate") in calls


def test_get_computed_blocks_given_insufficient_blocks_when_called_then_no_logging():
    mock_this = MagicMock()
    request = Request(request_id="req4", num_tokens=10)
    mock_original = MagicMock(return_value=(["block1"],))  # Single element tuple

    result = kvcache_hookers.get_computed_blocks(mock_original, mock_this, request)

    mock_original.assert_called_with(mock_this, request)
    assert result == (["block1"],)
    assert len(Profiler.instance_calls) == 0


def test_get_computed_blocks_given_zero_tokens_when_called_then_no_logging():
    mock_this = MagicMock()
    request = Request(request_id="req5", num_tokens=0)
    mock_original = MagicMock(return_value=(["block1", "block2"], 0))

    result = kvcache_hookers.get_computed_blocks(mock_original, mock_this, request)

    mock_original.assert_called_with(mock_this, request)
    assert result == (["block1", "block2"], 0)
    assert len(Profiler.instance_calls) == 0


def test_get_computed_blocks_given_negative_tokens_when_called_then_no_logging():
    mock_this = MagicMock()
    request = Request(request_id="req6", num_tokens=-5)
    mock_original = MagicMock(return_value=(["block1", "block2"], 3))

    result = kvcache_hookers.get_computed_blocks(mock_original, mock_this, request)

    mock_original.assert_called_with(mock_this, request)
    assert result == (["block1", "block2"], 3)
    assert len(Profiler.instance_calls) == 0


def test_get_computed_blocks_given_no_new_tokens_when_called_then_log_zero_hit_rate():
    mock_this = MagicMock()
    request = Request(request_id="req7", num_tokens=10)
    mock_original = MagicMock(return_value=(["block1", "block2"], 0))  # 0 new computed tokens

    result = kvcache_hookers.get_computed_blocks(mock_original, mock_this, request)

    mock_original.assert_called_with(mock_this, request)
    assert result == (["block1", "block2"], 0)
    assert len(Profiler.instance_calls) == 1
    calls = Profiler.instance_calls[0]
    assert ("attr", "hitCache", 0.0) in calls  # 0/10 = 0.0
