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

"""shm_manager version-mismatch and kill edge cases."""

import uuid
from unittest.mock import patch

import pytest

import ms_service_metric.utils.shm_manager as sm
from ms_service_metric.utils.shm_manager import SharedMemoryLayout, SharedMemoryManager

# 占位 PID：取 32 位有符号整型上限，远高于常见内核 pid_max，降低与真实进程碰撞的概率
# （若 mock 未生效，仍应避免误杀业务进程）
_FAKE_REMOTE_PID = 0x7FFFFFFF


@pytest.fixture
def prefix(monkeypatch):
    p = f"/ut_shm_ver_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("MS_SERVICE_METRIC_SHM_PREFIX", p)
    monkeypatch.setenv("MS_SERVICE_METRIC_MAX_PROCS", "8")
    return p


def test_version_mismatch_bad_magic(prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        mgr.write_int(SharedMemoryLayout.OFFSET_MAGIC, 0xDEADBEEF)
        mgr._check_version_compatibility()
        assert mgr._version_mismatch is True
    finally:
        mgr.destroy()


def test_version_mismatch_bad_header_end(prefix):
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        mgr.write_int(SharedMemoryLayout.OFFSET_HEADER_END, 0)
        mgr._check_version_compatibility()
        assert mgr._version_mismatch is True
    finally:
        mgr.destroy()


def test_send_signals_permission_error_skipped(prefix):
    # connect(create=True) 后应有有效进程表长度；用 assert 失败而非 skipif（模块级 skipif 无 connect/prefix 上下文）。
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        plen = mgr.get_proc_len()
        assert plen > 0, f"proc list expected after connect(create=True), got proc_len={plen}"
        mgr.set_proc_at(0, _FAKE_REMOTE_PID)
        with patch.object(sm.os, "kill", side_effect=PermissionError("nope")):
            sig, cl = mgr._send_signals_and_cleanup()
        assert sig == 0
    finally:
        mgr.destroy()


def test_send_signals_generic_failure_logged(prefix):
    # 同上：避免 plen<=0 时静默通过；不在收集阶段对未连接 mgr 做 skipif。
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        plen = mgr.get_proc_len()
        assert plen > 0, f"proc list expected after connect(create=True), got proc_len={plen}"
        mgr.set_proc_at(0, _FAKE_REMOTE_PID)

        def boom(*_a, **_k):
            raise OSError("weird")

        with patch.object(sm.os, "kill", side_effect=boom):
            mgr._send_signals_and_cleanup()
    finally:
        mgr.destroy()


def test_cleanup_invalid_permission_ok(prefix):
    """cleanup_invalid_processes：mock kill 抛 PermissionError 时仍应返回合法计数。

    plen<=0 时用 assert 失败，不用模块级 skipif：收集阶段未 connect、无 prefix，
    ``SharedMemoryManager().get_proc_len()`` 无意义。
    """
    # connect(create=True) 后进程表长度应为 max_procs；否则失败，避免 ``if plen > 0`` 静默跳过。
    mgr = SharedMemoryManager()
    assert mgr.connect(create=True) is True
    try:
        plen = mgr.get_proc_len()
        assert plen > 0, f"proc list expected after connect(create=True), got proc_len={plen}"
        mgr.set_proc_at(0, _FAKE_REMOTE_PID)
        with patch.object(sm.os, "kill", side_effect=PermissionError()):
            assert mgr.cleanup_invalid_processes() >= 0
    finally:
        mgr.destroy()


def test_connect_uses_actual_size_when_smaller_manager_expects_less(prefix):
    a = SharedMemoryManager()
    assert a.connect(create=True) is True
    try:
        b = SharedMemoryManager(max_procs=4)
        assert b.connect(create=False) is True
        try:
            assert b._memory_size == a._memory_size
        finally:
            b.disconnect()
    finally:
        a.destroy()
