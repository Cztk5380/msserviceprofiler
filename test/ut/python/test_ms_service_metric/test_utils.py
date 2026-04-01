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

from ms_service_metric.utils.function_context import FunctionContext


class TestFunctionContextGivenValidData:
    def test_when_create_context_then_local_values_is_none(self):
        ctx = FunctionContext()
        assert ctx.local_values is None
        assert ctx.return_value is None

    def test_when_set_local_values_then_values_are_stored(self):
        ctx = FunctionContext()
        ctx.local_values = {"x": 1, "y": 2}
        assert ctx.local_values == {"x": 1, "y": 2}

    def test_when_set_return_value_then_value_is_stored(self):
        ctx = FunctionContext()
        ctx.return_value = "test_result"
        assert ctx.return_value == "test_result"

    def test_when_get_existing_key_then_return_value(self):
        ctx = FunctionContext()
        ctx.local_values = {"key": "value"}
        assert ctx.get("key") == "value"

    def test_when_get_nonexistent_key_with_default_then_return_default(self):
        ctx = FunctionContext()
        ctx.local_values = {}
        assert ctx.get("missing", "default") == "default"

    def test_when_get_nonexistent_key_without_default_then_return_none(self):
        ctx = FunctionContext()
        ctx.local_values = {}
        assert ctx.get("missing") is None

    def test_when_getitem_with_existing_key_then_return_value(self):
        ctx = FunctionContext()
        ctx.local_values = {"key": "value"}
        assert ctx["key"] == "value"

    def test_when_getitem_with_nonexistent_key_then_raise_key_error(self):
        ctx = FunctionContext()
        ctx.local_values = {}
        with pytest.raises(KeyError):
            _ = ctx["missing"]

    def test_when_contains_with_existing_key_then_return_true(self):
        ctx = FunctionContext()
        ctx.local_values = {"key": "value"}
        assert "key" in ctx

    def test_when_contains_with_nonexistent_key_then_return_false(self):
        ctx = FunctionContext()
        ctx.local_values = {}
        assert "missing" not in ctx

    def test_when_contains_with_none_local_values_then_return_false(self):
        ctx = FunctionContext()
        assert "key" not in ctx

    def test_when_get_with_none_local_values_then_return_default(self):
        ctx = FunctionContext()
        assert ctx.get("key", "default") == "default"

