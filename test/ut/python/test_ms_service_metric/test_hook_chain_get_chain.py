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

from unittest.mock import patch

from ms_service_metric.core.hook.hook_chain import HookChain, get_chain


def test_given_callable_when_get_chain_twice_then_same_hook_chain_instance():
    def f():
        return 1

    c1 = get_chain(f)
    c2 = get_chain(f)
    assert isinstance(c1, HookChain)
    assert c1 is c2


def test_given_builtin_callable_when_get_chain_then_warns_uncacheable_and_returns_chain():
    with patch("ms_service_metric.core.hook.hook_chain.logger") as mock_logger:
        c = get_chain(len)
        assert isinstance(c, HookChain)
        mock_logger.warning.assert_called_once()
        msg = mock_logger.warning.call_args[0][0]
        assert "Cannot cache hook chain" in msg
