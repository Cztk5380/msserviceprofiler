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

"""Unit tests for ms_service_metric.metrics.meta_state."""

import threading

from ms_service_metric.metrics.meta_state import (
    MetaState,
    get_dp_rank,
    get_meta_state,
    get_model_name,
    reset_meta_state,
    set_dp_rank,
    set_model_name,
)


def test_meta_state_get_set_update_remove_clear():
    """MetaState 基本 CRUD：get/set/update/remove/clear。"""
    m = MetaState()
    assert m.get("k") is None
    assert m.get("k", "d") == "d"
    m.set("a", 1)
    assert m.get("a") == 1
    m.update({"b": 2, "c": 3})
    assert m.get_all() == {"a": 1, "b": 2, "c": 3}
    assert m.has("b") is True
    assert m.remove("b") is True
    assert m.has("b") is False
    assert m.remove("b") is False
    m.clear()
    assert m.get_all() == {}


def test_meta_state_dp_rank_and_model_name_properties():
    """实例属性 dp_rank、model_name 与内部存储一致。"""
    m = MetaState()
    assert m.dp_rank == -1
    assert m.model_name == "unknown"
    m.dp_rank = 7
    m.model_name = "m1"
    assert m.dp_rank == 7
    assert m.model_name == "m1"


def test_helpers_use_global_meta_state():
    """全局单例 helper：读写后与 get_meta_state 为同一对象；结束后 reset 避免污染其他用例。"""
    reset_meta_state()
    try:
        set_dp_rank(3)
        set_model_name("x")
        assert get_dp_rank() == 3
        assert get_model_name() == "x"
        ms = get_meta_state()
        assert ms is get_meta_state()
    finally:
        reset_meta_state()


def test_meta_state_thread_safety():
    """多线程并发 set：无异常且最终键数量符合预期。"""
    m = MetaState()
    errors = []
    n_threads = 4
    span = 100

    def writer(start: int, end: int) -> None:
        try:
            for i in range(start, end):
                m.set(f"key_{i}", i)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=writer, args=(i * span, (i + 1) * span))
        for i in range(n_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(m.get_all()) == n_threads * span
