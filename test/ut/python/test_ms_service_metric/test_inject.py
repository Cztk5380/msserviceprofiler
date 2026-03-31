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

try:
    from bytecode import Bytecode, Instr  # noqa: F401

    BYTECODE_AVAILABLE = True
except ImportError:
    BYTECODE_AVAILABLE = False


@pytest.mark.skipif(not BYTECODE_AVAILABLE, reason="bytecode library not available")
class TestInject:
    def test_given_simple_function_when_inject_then_hooks_called(self):
        from ms_service_metric.core.hook.inject import inject_function

        hook_calls = []

        def context_factory(ctx):
            class TestContext:
                def __enter__(self):
                    hook_calls.append("enter")
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    hook_calls.append("exit")
                    return False

            return TestContext()

        def original_func(x):
            hook_calls.append(f"ori_{x}")
            return x * 2

        injected = inject_function(original_func, [context_factory])

        result = injected(5)

        assert "enter" in hook_calls
        assert "ori_5" in hook_calls
        assert "exit" in hook_calls
        assert result == 10
