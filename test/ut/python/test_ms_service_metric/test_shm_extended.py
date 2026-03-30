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

"""Additional SharedMemoryManager / shm helpers coverage."""

import uuid
from unittest.mock import patch

import pytest

from ms_service_metric.utils import shm_manager as shm_mod
from ms_service_metric.utils.shm_manager import (
    STATE_OFF,
    STATE_ON,
    SharedMemoryLayout,
    SharedMemoryManager,
    get_sem_name,
    get_shm_name,
)


@pytest.fixture
def shm_prefix(monkeypatch):
    p = f"/ut_shm_ext_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MS_SERVICE_METRIC_SHM_PREFIX", p)
    monkeypatch.setenv("MS_SERVICE_METRIC_MAX_PROCS", "8")
    return p


def _clear_all_proc_slots(mgr: SharedMemoryManager) -> None:
    """将共享内存进程表每一槽位置 0，表示无登记 PID（用于构造「无存活 worker」场景）。"""
    proc_len = mgr.get_proc_len()
    if proc_len <= 0:
        return
    for i in range(proc_len):
        mgr.set_proc_at(i, 0)


def test_get_shm_sem_name_helpers():
    assert get_shm_name("/x") == "/x_control"
    assert get_sem_name("/x") == "/x_semaphore"


def test_send_control_no_op_when_already_in_state(shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        mgr.set_state(STATE_ON)
        ok, sig, cl, changed = mgr.send_control_command(is_start=True, force=False, send_signal=False)
        assert ok and changed is False and sig == 0
    finally:
        mgr.destroy()


def test_send_control_updates_and_skips_signal(shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        mgr.set_state(STATE_OFF)
        ok, sig, cl, changed = mgr.send_control_command(
            is_start=True, force=False, send_signal=False
        )
        assert ok and changed is True
        assert mgr.get_state() == STATE_ON
    finally:
        mgr.destroy()


def test_send_control_force_from_on_to_on(shm_prefix):
    """已在 ON 时 force 再开：应视为有变更并走信号路径（此处 mock 掉实际发信号）。"""
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        mgr.set_state(STATE_ON)
        with patch.object(mgr, "_send_signals_and_cleanup", return_value=(0, 0)):
            ok, _, _, changed = mgr.send_control_command(
                is_start=True, force=True, send_signal=True
            )
        assert ok and changed is True
    finally:
        mgr.destroy()


def test_add_current_process_and_get_status(shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        with patch.object(shm_mod.os, "kill", return_value=None):
            idx = mgr.add_current_process()
            assert idx >= 0
            st = mgr.get_status()
            assert st["state"] in ("ON", "OFF")
            assert "process_count" in st
    finally:
        mgr.destroy()


def test_should_destroy_when_off_and_empty(shm_prefix):
    """OFF 且进程表可清空时应销毁；OFF 但仍有合法 worker 时不应销毁。"""
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        mgr.set_state(STATE_OFF)
        plen = mgr.get_proc_len()
        assert plen > 0, f"proc list expected after connect(create=True), got proc_len={plen}"
        with patch.object(shm_mod.os, "kill", return_value=None):
            mgr.add_current_process()
        assert mgr.should_destroy() is False
        _clear_all_proc_slots(mgr)
        assert mgr.get_state() == STATE_OFF
        assert mgr.get_all_procs() == []
        assert mgr.should_destroy() is True
        with patch.object(shm_mod.os, "kill", return_value=None):
            mgr.add_current_process()
        assert mgr.should_destroy() is False
    finally:
        mgr.destroy()


def test_version_mismatch_on_reconnect(shm_prefix):
    """头部版本号与当前实现不一致时，新连接应标记 _version_mismatch。"""
    a = SharedMemoryManager()
    assert a.connect(create=True) is True
    try:
        a.write_int(SharedMemoryLayout.OFFSET_VERSION, 99999)
        b = SharedMemoryManager()
        assert b.connect(create=False) is True
        try:
            assert b._version_mismatch is True
        finally:
            b.disconnect()
    finally:
        a.destroy()


def test_get_all_procs_dedup(shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        plen = mgr.get_proc_len()
        assert plen > 0, f"proc list expected after connect(create=True), got proc_len={plen}"
        # plen > 1：两槽同 PID 验证去重；否则单槽仍执行 get_all_procs，避免 plen<=1 时空跑
        if plen > 1:
            mgr.set_proc_at(0, 42)
            mgr.set_proc_at(1, 42)
            assert sorted(mgr.get_all_procs()) == [42]
        else:
            mgr.set_proc_at(0, 42)
            assert mgr.get_all_procs() == [42]
    finally:
        mgr.destroy()


def test_update_state_and_timestamp(shm_prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        mgr.update_state_and_timestamp(STATE_ON)
        assert mgr.get_state() == STATE_ON
        assert mgr.get_timestamp() > 0
    finally:
        mgr.destroy()
