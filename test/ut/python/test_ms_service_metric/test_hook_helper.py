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

from ms_service_metric.core.hook.hook_helper import HookHelper


class TestHookHelper:
    def test_given_simple_function_when_hook_then_replace_and_recover(self):
        original_calls = []
        hook_calls = []

        class TestClass:
            def method(self, x):
                original_calls.append(x)
                return x * 2

        obj = TestClass()
        original = obj.method

        def hook_func(*args, **kwargs):
            hook_calls.append("hook")
            return original(*args, **kwargs) + 1

        helper = HookHelper(original, hook_func)
        helper.replace()

        result = obj.method(5)
        assert result == 11
        assert "hook" in hook_calls

        helper.recover()

        result = obj.method(5)
        assert result == 10

    def test_given_hook_applied_when_replace_again_then_ignore(self):
        class TestClass:
            def method(self, x):
                return x * 2

        obj = TestClass()
        original = obj.method
        hook_func = lambda *args, **kwargs: original(*args, **kwargs)

        helper = HookHelper(obj.method, hook_func)
        helper.replace()
        helper.replace()

        assert helper.is_replaced is True
        helper.recover()

    def test_given_no_hook_applied_when_recover_then_ignore(self):
        class TestClass:
            def method(self, x):
                return x * 2

        obj = TestClass()
        original = obj.method
        hook_func = lambda *args, **kwargs: original(*args, **kwargs)

        helper = HookHelper(obj.method, hook_func)
        helper.recover()

        assert helper.is_replaced is False
