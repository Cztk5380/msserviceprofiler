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

import time
from contextlib import contextmanager

import pytest

pytest.importorskip("ms_service_metric.metrics.metrics_manager")

from ms_service_metric.handlers.builtin import default_handler
from ms_service_metric.metrics.metrics_manager import MetricConfig, MetricType, get_metrics_manager
from ms_service_metric.utils.function_context import FunctionContext


def test_given_default_handler_without_locals_when_wrap_original_then_timer_observed():
    manager = get_metrics_manager()

    metrics_config = [MetricConfig(name="t_no_locals", type=MetricType.TIMER)]
    timer_factory = default_handler(metrics_config, is_async=False)

    def ori(x):
        return x * 2

    res = timer_factory(ori, 3)
    assert res == 6

    metric_obj = manager.get_all_metrics().get("t_no_locals")
    assert metric_obj is not None
    assert metric_obj._last_observe is not None


def test_given_default_handler_with_label_exprs_when_context_exits_then_timer_has_evaluated_labels():
    manager = get_metrics_manager()

    metrics_config = [
        MetricConfig(
            name="t_with_labels",
            type=MetricType.TIMER,
            labels={"status": "ret['status']"},
        )
    ]
    timer_ctx_factory = default_handler(metrics_config, is_async=False)

    ctx = FunctionContext()
    ctx.return_value = {"status": "success"}
    ctx.local_values = {"unused": 123}

    with contextmanager(timer_ctx_factory)(ctx):
        time.sleep(0.001)

    metric_obj = manager.get_all_metrics().get("t_with_labels")
    assert metric_obj is not None
    assert metric_obj._last_observe is not None
    assert metric_obj._last_labels["status"] == "success"

import asyncio


@pytest.mark.asyncio
async def test_given_default_handler_async_when_wrap_original_then_timer_observed():
    manager = get_metrics_manager()

    metrics_config = [MetricConfig(name="t_async", type=MetricType.TIMER)]
    timer_factory = default_handler(metrics_config, is_async=True)

    async def async_ori(x):
        await asyncio.sleep(0.001)
        return x * 2

    res = await timer_factory(async_ori, 3)
    assert res == 6

    metric_obj = manager.get_all_metrics().get("t_async")
    assert metric_obj is not None
    assert metric_obj._last_observe is not None


def test_given_default_handler_with_multiple_metrics_when_wrap_original_then_all_metrics_observed():
    manager = get_metrics_manager()

    metrics_config = [
        MetricConfig(name="t_multi_1", type=MetricType.TIMER),
        MetricConfig(name="t_multi_2", type=MetricType.TIMER),
    ]
    timer_factory = default_handler(metrics_config, is_async=False)

    def ori(x):
        return x * 2

    res = timer_factory(ori, 3)
    assert res == 6

    metric_obj1 = manager.get_all_metrics().get("t_multi_1")
    metric_obj2 = manager.get_all_metrics().get("t_multi_2")
    assert metric_obj1 is not None
    assert metric_obj2 is not None
    assert metric_obj1._last_observe is not None
    assert metric_obj2._last_observe is not None


def test_given_default_handler_with_invalid_label_expr_when_context_exits_then_handles_gracefully():
    manager = get_metrics_manager()

    metrics_config = [
        MetricConfig(
            name="t_invalid_label",
            type=MetricType.TIMER,
            labels={"status": "ret['missing']['x']"},
        )
    ]
    timer_ctx_factory = default_handler(metrics_config, is_async=False)

    ctx = FunctionContext()
    ctx.return_value = {"status": "success"}
    ctx.local_values = {}

    with contextmanager(timer_ctx_factory)(ctx):
        time.sleep(0.001)

    metric_obj = manager.get_all_metrics().get("t_invalid_label")
    assert metric_obj is not None

import asyncio


def test_given_default_handler_async_when_wrap_original_then_timer_observed():
    manager = get_metrics_manager()
    metrics_config = [MetricConfig(name='t_async', type=MetricType.TIMER)]
    timer_factory = default_handler(metrics_config, is_async=True)

    async def async_ori(x):
        await asyncio.sleep(0.001)
        return x * 2

    res = asyncio.run(timer_factory(async_ori, 3))
    assert res == 6

    metric_obj = manager.get_all_metrics().get('t_async')
    assert metric_obj is not None
    assert metric_obj._last_observe is not None
