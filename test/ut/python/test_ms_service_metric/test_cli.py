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

"""Tests for ms_service_metric.control.cli."""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_manager():
    with patch("ms_service_metric.control.cli.SharedMemoryManager") as m:
        inst = MagicMock()
        m.return_value = inst
        yield inst


def test_send_control_command_on_success(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = True
    mock_manager.send_control_command.return_value = (True, 2, 1, True)
    mock_manager.should_destroy.return_value = False

    assert cli.send_control_command("on", "/ut_cli", 8) == 0
    mock_manager.connect.assert_called_once_with(create=True)
    mock_manager.send_control_command.assert_called_once()


def test_send_control_command_off_no_shm(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = False
    assert cli.send_control_command("off", "/ut_cli", 8) == 0
    mock_manager.send_control_command.assert_not_called()


def test_send_control_command_on_connect_fails(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = False
    assert cli.send_control_command("on", "/ut_cli", 8) == 1


def test_send_control_command_send_fails(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = True
    mock_manager.send_control_command.return_value = (False, 0, 0, False)
    assert cli.send_control_command("restart", "/ut_cli", 8) == 1


def test_send_control_off_releases_when_should_destroy(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = True
    mock_manager.send_control_command.return_value = (True, 0, 0, True)
    mock_manager.should_destroy.return_value = True

    assert cli.send_control_command("off", "/ut_cli", 8) == 0
    mock_manager.destroy.assert_called_once()


def test_send_control_no_change_message(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = True
    mock_manager.send_control_command.return_value = (True, 0, 0, False)

    assert cli.send_control_command("on", "/ut_cli", 8) == 0


def test_send_control_exception_returns_1(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.side_effect = RuntimeError("boom")
    assert cli.send_control_command("on", "/ut_cli", 8) == 1


def test_show_status_no_shm(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = False
    assert cli.show_status("/ut_cli", 8) == 0


def test_show_status_with_procs(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = True
    mock_manager.get_status.return_value = {
        "state": "ON",
        "timestamp": 9,
        "process_cursor": 0,
        "process_list_len": 4,
        "process_count": 12,
        "processes": list(range(12)),
        "cleaned": 0,
        "version_mismatch": False,
    }
    assert cli.show_status("/ut_cli", 4) == 0


def test_show_status_version_mismatch_and_cleanup(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.return_value = True
    mock_manager.get_status.return_value = {
        "state": "OFF",
        "timestamp": 0,
        "process_cursor": 0,
        "process_list_len": 4,
        "process_count": 0,
        "processes": [],
        "cleaned": 3,
        "version_mismatch": True,
    }
    mock_manager.should_destroy.return_value = True
    assert cli.show_status("/ut_cli", 8) == 0
    mock_manager.destroy.assert_called_once()


def test_show_status_exception(mock_manager):
    from ms_service_metric.control import cli

    mock_manager.connect.side_effect = OSError("x")
    assert cli.show_status("/ut_cli", 8) == 1


def test_main_routes_status():
    from ms_service_metric.control import cli

    with patch.object(sys, "argv", ["ms-service-metric", "status", "--shm-prefix", "/a", "--max-procs", "3"]):
        with patch.object(cli, "show_status", return_value=0) as st:
            assert cli.main() == 0
            st.assert_called_once_with("/a", 3)


def test_main_routes_control():
    from ms_service_metric.control import cli

    with patch.object(sys, "argv", ["ms-service-metric", "off", "--shm-prefix", "/b"]):
        with patch.object(cli, "send_control_command", return_value=0) as sc:
            assert cli.main() == 0
            sc.assert_called_once()


def test_main_posix_unavailable():
    from ms_service_metric.control import cli

    with patch.object(cli, "POSIX_IPC_AVAILABLE", False):
        with patch.object(sys, "argv", ["ms-service-metric", "status"]):
            assert cli.main() == 1
