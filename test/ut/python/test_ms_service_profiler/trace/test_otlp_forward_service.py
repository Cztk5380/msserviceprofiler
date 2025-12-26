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

import signal
import pytest
from unittest.mock import MagicMock, patch, call
from ms_service_profiler.tracer.otlp_forward_service import OTLPForwarderService


@pytest.fixture
def mock_check_export():
    """Mock the check_export_initialization function"""
    with patch("ms_service_profiler.tracer.otlp_forward_service.check_export_initialization") as mock:
        yield mock


@pytest.fixture
def mock_socket_server():
    """Mock the socket class"""
    with patch("ms_service_profiler.tracer.otlp_forward_service.AbstractSocketServer") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_cls, mock_instance


@pytest.fixture
def mock_scheduler():
    """Mock the Scheduler class"""
    with patch("ms_service_profiler.tracer.otlp_forward_service.Scheduler") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_cls, mock_instance


@pytest.fixture
def mock_signal():
    """Mock the signal module"""
    with patch("ms_service_profiler.tracer.otlp_forward_service.signal.signal") as mock:
        yield mock


class TestOTLPForwarderService:
    def test_init_success(self, mock_check_export, mock_socket_server, mock_scheduler, mock_signal):
        """Test successful initialization scenario"""
        mock_check_export.return_value = True
        mock_socket_cls, mock_socket_instance = mock_socket_server
        mock_scheduler_cls, _ = mock_scheduler
        service = OTLPForwarderService()
        mock_check_export.assert_called_once()
        mock_socket_cls.assert_called_with(
            socket_name="OTLP_SOCKET",
            buffer_size=4096,
            max_listen_num=8,
            socket_timeout=1,
            max_queue_size=1000000,
            warning_queue_size=100000
        )
        mock_scheduler_cls.assert_called_with(
            interval=1,
            socket_server=mock_socket_instance
        )
        mock_signal.assert_has_calls([
            call(signal.SIGINT, service._handle_signal),
            call(signal.SIGTERM, service._handle_signal)
        ])

    def test_start_exception(
            self,
            mock_check_export,
            mock_socket_server,
            mock_scheduler
    ):
        """Test start method exception handling"""
        mock_check_export.return_value = True
        service = OTLPForwarderService()
        _, mock_socket_instance = mock_socket_server
        mock_socket_instance.start.side_effect = Exception("Socket start failed")

        service.start()
        mock_socket_instance.start.assert_called_once()
        mock_socket_instance.stop.assert_called_once()

    def test_stop(self, mock_check_export, mock_socket_server, mock_scheduler):
        """Test stop method"""
        mock_check_export.return_value = True
        service = OTLPForwarderService()
        _, mock_socket_instance = mock_socket_server
        _, mock_scheduler_instance = mock_scheduler
        service.stop()
        mock_scheduler_instance.stop.assert_called_once()
        mock_socket_instance.stop.assert_called_once()