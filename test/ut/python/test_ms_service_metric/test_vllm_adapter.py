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

import pytest

import ms_service_metric.adapters.vllm.adapter as adapter_module
from ms_service_metric.adapters.vllm.adapter import VLLMMetricAdapter


@pytest.mark.parametrize(
    ("process_name", "expected"),
    [
        ("EngineCore_DP0", 0),
        ("EngineCore_DP1", 1),
        ("(EngineCore_DP2 pid=1234)", 2),
        ("EngineCore-DP3", 3),
        ("ApiServer_1", -1),
        ("Worker", -1),
    ],
)
def test_parse_dp_rank_from_process_name(process_name, expected):
    assert VLLMMetricAdapter._parse_dp_rank_from_process_name(process_name) == expected


def test_setup_dp_rank_uses_env_first(monkeypatch):
    captured = []
    adapter = VLLMMetricAdapter()

    monkeypatch.setenv("VLLM_DP_RANK", "2")
    monkeypatch.setattr(adapter_module, "set_dp_rank", captured.append)
    monkeypatch.setattr(adapter, "_get_dp_rank_from_vllm", lambda: pytest.fail("vLLM fallback should not run"))
    monkeypatch.setattr(adapter, "_get_dp_rank_from_process_name", lambda: pytest.fail("process fallback should not run"))

    adapter._setup_dp_rank()

    assert captured == [2]


def test_setup_dp_rank_falls_back_to_process_name(monkeypatch):
    captured = []
    adapter = VLLMMetricAdapter()

    monkeypatch.delenv("VLLM_DP_RANK", raising=False)
    monkeypatch.setattr(adapter_module, "set_dp_rank", captured.append)
    monkeypatch.setattr(adapter, "_get_dp_rank_from_vllm", lambda: -1)
    monkeypatch.setattr(adapter, "_get_dp_rank_from_process_name", lambda: 1)

    adapter._setup_dp_rank()

    assert captured == [1]
