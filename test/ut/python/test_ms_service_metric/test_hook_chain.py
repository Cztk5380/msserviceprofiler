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

from ms_service_metric.core.hook.hook_chain import get_chain


CALLS = []


def target_func(x, y):
    CALLS.append("original")
    return x + y


def test_given_chain_without_nodes_when_exec_closure_then_runs_original_and_returns_sum():
    chain = get_chain(target_func)
    execute = chain.exec_chain_closure()
    assert execute(1, 2) == 3


def test_given_two_head_wrap_nodes_when_call_patched_global_then_hooks_run_in_order_with_offsets():
    global CALLS
    CALLS = []

    chain = get_chain(target_func)
    node1 = chain.add_chain_node(insert_at_head=True)

    def hook1(*args, **kwargs):
        CALLS.append("hook1_before")
        res = node1.ori_wrap(*args, **kwargs)
        CALLS.append("hook1_after")
        return res + 1

    node1.set_hook_func(hook1)

    node2 = chain.add_chain_node(insert_at_head=True)

    def hook2(*args, **kwargs):
        CALLS.append("hook2_before")
        res = node2.ori_wrap(*args, **kwargs)
        CALLS.append("hook2_after")
        return res + 10

    node2.set_hook_func(hook2)

    assert target_func(5, 0) == 5 + 10 + 1
    assert CALLS[0] == "hook1_before"
    assert "original" in CALLS
    assert CALLS[-1] == "hook1_after"

    node2.remove()
    node1.remove()

import pytest
import threading
import time


def test_given_hook_raises_exception_when_executed_then_falls_back_to_original_result():
    chain = get_chain(target_func)
    node = chain.add_chain_node(insert_at_head=True)

    def hook_with_exception(*args, **kwargs):
        raise RuntimeError('hook exception')

    node.set_hook_func(hook_with_exception)
    try:
        # HookChain 内部有异常保护，会回退调用原函数
        assert target_func(1, 2) == 3
    finally:
        node.remove()


def test_given_node_removed_when_call_original_then_runs_without_hook():
    global CALLS
    CALLS = []

    chain = get_chain(target_func)
    node = chain.add_chain_node(insert_at_head=True)

    def hook(*args, **kwargs):
        CALLS.append('hook')
        return node.ori_wrap(*args, **kwargs)

    node.set_hook_func(hook)

    try:
        _ = target_func(1, 2)
        assert 'hook' in CALLS
    finally:
        node.remove()

    CALLS = []
    result2 = target_func(3, 4)
    assert 'hook' not in CALLS
    assert result2 == 7


def test_given_concurrent_add_remove_when_multiple_threads_then_thread_safe():
    chain = get_chain(target_func)
    initial_count = len(chain._nodes)

    def add_and_remove_node():
        node = chain.add_chain_node(insert_at_head=True)
        try:
            time.sleep(0.001)
        finally:
            node.remove()

    threads = [threading.Thread(target=add_and_remove_node) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(chain._nodes) == initial_count
