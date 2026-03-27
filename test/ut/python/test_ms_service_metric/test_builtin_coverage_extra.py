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

"""handlers/builtin.py extra branches."""

import asyncio
from unittest.mock import MagicMock

import pytest

from ms_service_metric.handlers import builtin


def test_get_labels_skips_empty_expr():
    out = builtin._get_labels_for_metric(
        "m",
        {"x": 1},
        {"m": [{"name": "a", "expr": ""}, {"name": "b", "expr": "x"}]},
    )
    assert "a" not in out and out.get("b") == "1"


def test_get_labels_eval_failure_continues():
    out = builtin._get_labels_for_metric(
        "m",
        {},
        {"m": [{"name": "a", "expr": "no_such_name * 2"}]},
    )
    assert out == {}


def test_default_handler_async_timer():
    h = builtin.default_handler([{"name": "atimer_ut", "type": "timer"}], is_async=True)

    async def ori():
        return 42

    async def run():
        return await h(ori)

    assert asyncio.run(run()) == 42


def test_default_handler_need_locals_generator():
    h = builtin.default_handler(
        [{"name": "lt_ut", "type": "timer", "expr": "duration"}]
    )
    assert callable(h)
    ctx = MagicMock()
    ctx.local_values = {}
    ctx.return_value = None
    gen = h(ctx)
    assert gen is not None
    next(gen)
    ctx.local_values = {"duration": 0.01}
    try:
        next(gen)
    except StopIteration:
        pass


def test_default_handler_gauge_sync_no_expr():
    h = builtin.default_handler([{"name": "gauge_ut", "type": "gauge"}])
    assert h(lambda: 1) == 1


def test_default_handler_label_expr_compile_fail():
    builtin.default_handler(
        [
            {
                "name": "lb_ut",
                "type": "timer",
                "labels": {"bad": "(((notvalid"},
            }
        ]
    )


def test_default_handler_main_expr_compile_fail():
    builtin.default_handler(
        [{"name": "ex_ut", "type": "gauge", "expr": "syntax error here"}]
    )


def test_record_branch_counter_sync_no_expr():
    h = builtin.default_handler([{"name": "cnt_ut", "type": "counter"}])
    assert h(lambda: 7) == 7
