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

"""tests for adapters/vllm/metrics_init (no real vLLM dependency)."""

from unittest.mock import MagicMock

import ms_service_metric.adapters.vllm.metrics_init as mi
from ms_service_metric.metrics.metrics_manager import get_metrics_manager


def test_setup_vllm_metrics_sets_prefix_when_vllm_unavailable(monkeypatch):
    monkeypatch.setattr(mi, "VLLM_METRICS_AVAILABLE", False)
    client = get_metrics_manager()
    client.metric_prefix = ""
    mi.setup_vllm_metrics()
    assert client.metric_prefix == mi.VLLM_METRICS_PREFIX


def test_set_vllm_multiprocess_warns_without_env(monkeypatch):
    monkeypatch.setattr(mi, "VLLM_METRICS_AVAILABLE", True)
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    mi.set_vllm_multiprocess_prometheus()


def test_set_vllm_registry_when_available(monkeypatch):
    fake_reg = MagicMock(name="fake_registry")
    monkeypatch.setattr(mi, "VLLM_METRICS_AVAILABLE", True)
    monkeypatch.setattr(mi, "get_prometheus_registry", lambda: fake_reg)
    client = get_metrics_manager()
    mi.set_vllm_registry(client)
    assert client.get_registry() is fake_reg


def test_set_vllm_registry_swallows_errors(monkeypatch):
    monkeypatch.setattr(mi, "VLLM_METRICS_AVAILABLE", True)

    def boom():
        raise RuntimeError("no registry")

    monkeypatch.setattr(mi, "get_prometheus_registry", boom)
    client = get_metrics_manager()
    mi.set_vllm_registry(client)
