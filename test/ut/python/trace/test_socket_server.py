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

import socket
import ctypes
import queue
import pytest
from unittest.mock import Mock, patch
from ms_service_profiler.tracer.socket_server import AbstractSocketServer, Ucred, OTEL_Length_Field


server = None


@pytest.fixture(autouse=True)
def create_and_reset_server():
    """Create and reset the socket_server before and after each test case"""
    global server
    server = AbstractSocketServer(socket_name="test_socket", buffer_size=4096, max_listen_num=5, socket_timeout=10)
    yield
    server = None


class TestSocketServer:
    global server

    def test_initialization(self):
        """Test initialization logic"""

        assert server.socket_name == "\0test_socket"
        assert server.buffer_size == 4096
        assert server.max_listen_num == 5
        assert server.socket_timeout == 10
        assert isinstance(server.data_queue, queue.Queue)
        assert server.running is False
        assert server.server_socket is None
        assert server.thread is None


    @patch("socket.socket")
    def test_create_socket_success(self, mock_socket_class):
        """Test successful socket creation scenario"""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock
        sock = server._create_socket()
        mock_socket_class.assert_called_once_with(socket.AF_UNIX, socket.SOCK_STREAM)
        mock_sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_sock.bind.assert_called_once_with("\0test_socket")
        mock_sock.listen.assert_called_once_with(5)
        assert sock == mock_sock


    @patch("socket.socket")
    def test_create_socket_failure(self, mock_socket_class):
        """Test socket creation failure scenario"""
        mock_sock = Mock()
        mock_sock.fileno.return_value = 1
        mock_socket_class.return_value = mock_sock
        mock_sock.bind.side_effect = Exception("Bind failed")
        with pytest.raises(Exception, match="Bind failed"):
            server._create_socket()
        mock_sock.close.assert_called_once()

    @patch.object(AbstractSocketServer, "_get_namespace_inode")
    @patch("os.getpid")
    @patch("os.getgid")
    @patch("os.getuid")
    def test_validate_peer_cred_success(self, mock_getuid, mock_getgid, mock_getpid, mock_get_namespace_inode):
        """Test successful peer credential validation scenario"""
        mock_getuid.return_value = 1000
        mock_getgid.return_value = 1000
        mock_getpid.return_value = 2345
        mock_get_namespace_inode.side_effect = ["22", "22", "33", "33"]
        mock_client_sock = Mock()
        mock_cred = Ucred()
        mock_cred.pid = 1234
        mock_cred.uid = 1000
        mock_cred.gid = 1000
        cred_data = bytes(mock_cred)
        mock_client_sock.getsockopt.return_value = cred_data
        result = server._validate_peer_cred(mock_client_sock)
        mock_client_sock.getsockopt.assert_called_once_with(socket.SOL_SOCKET, 17, ctypes.sizeof(Ucred))
        assert result is True


    @patch("os.getuid")
    def test_validate_peer_cred_uid_mismatch(self, mock_getuid):
        """Test peer credential UID mismatch scenario"""
        mock_getuid.return_value = 1000
        mock_client_sock = Mock()
        mock_cred = Ucred()
        mock_cred.uid = 2000
        cred_data = bytes(mock_cred)
        mock_client_sock.getsockopt.return_value = cred_data
        result = server._validate_peer_cred(mock_client_sock)
        assert result is False


    def test_validate_peer_cred_exception(self):
        """Test peer credential retrieval exception scenario"""
        mock_client_sock = Mock()
        mock_client_sock.getsockopt.side_effect = Exception("Get cred failed")
        result = server._validate_peer_cred(mock_client_sock)
        assert result is False


    @patch.object(AbstractSocketServer, "_get_namespace_inode")
    @patch("os.getpid")
    @patch("os.getgid")
    @patch("os.getuid")
    def test_validate_peer_cred_namespace_mismatch(
            self, mock_getuid, mock_getgid, mock_getpid, mock_get_namespace_inode):
        """Test peer credential namespace mismatch scenario"""
        mock_getuid.return_value = 1000
        mock_getgid.return_value = 1000
        mock_getpid.return_value = 2345
        mock_get_namespace_inode.side_effect = ["22", "22", "33", "44"]
        mock_client_sock = Mock()
        mock_cred = Ucred()
        mock_cred.pid = 1234
        mock_cred.uid = 1000
        mock_cred.gid = 1000
        cred_data = bytes(mock_cred)
        mock_client_sock.getsockopt.return_value = cred_data
        result = server._validate_peer_cred(mock_client_sock)
        mock_client_sock.getsockopt.assert_called_once_with(socket.SOL_SOCKET, 17, ctypes.sizeof(Ucred))
        assert result is False


    def test_handle_recv_complete_frame(self):
        """Test complete data frame reception"""
        mock_client_sock = Mock()
        mock_client_sock.recv.side_effect = [
            b"\x00\x00\x00\x05hello",
            b""
        ]
        remaining_buffer = server._handle_recv(mock_client_sock, OTEL_Length_Field)
        assert server.data_queue.qsize() == 1
        assert server.data_queue.get() == b"hello"
        assert remaining_buffer == b""


    def test_handle_recv_chunked_frame(self):
        """Test chunked data frame reception"""
        mock_client_sock = Mock()
        mock_client_sock.recv.side_effect = [
            b"\x00\x00\x00\x05",
            b"hello",
            b""
        ]
        server._handle_recv(mock_client_sock, OTEL_Length_Field)
        assert server.data_queue.qsize() == 1
        assert server.data_queue.get() == b"hello"


    def test_handle_recv_incomplete_frame(self):
        """Test incomplete data frame reception"""
        mock_client_sock = Mock()
        mock_client_sock.recv.side_effect = [
            b"\x00\x00\x00\x05hel",
            b""
        ]
        remaining_buffer = server._handle_recv(mock_client_sock, OTEL_Length_Field)

        assert server.data_queue.empty()
        assert remaining_buffer == b"\x00\x00\x00\x05hel"


    @patch.object(AbstractSocketServer, "_validate_peer_cred")
    @patch.object(AbstractSocketServer, "_handle_recv")
    def test_handle_client_cred_failure(self, mock_handle_recv, mock_validate_peer_cred):
        """Test client credential validation failure"""
        mock_validate_peer_cred.return_value = False
        mock_client_sock = Mock()
        server._handle_client(mock_client_sock, "client_addr")
        mock_handle_recv.assert_not_called()


    @patch.object(AbstractSocketServer, "_validate_peer_cred")
    @patch.object(AbstractSocketServer, "_handle_recv")
    def test_handle_client_cred_success(self, mock_handle_recv, mock_validate_peer_cred):
        """Test client credential validation success"""
        mock_validate_peer_cred.return_value = True
        mock_handle_recv.return_value = b"remaining_data"
        mock_client_sock = Mock()
        server._handle_client(mock_client_sock, "client_addr")
        mock_handle_recv.assert_called_once_with(mock_client_sock, OTEL_Length_Field)


    @patch.object(AbstractSocketServer, "_create_socket")
    @patch("threading.Thread")
    def test_start_server(self, mock_thread_class, mock_create_socket):
        """Test server start"""
        mock_sock = Mock()
        mock_create_socket.return_value = mock_sock
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread
        server.start()
        assert server.running is True
        mock_create_socket.assert_called_once()
        mock_thread_class.assert_called_once_with(target=server._server_loop, daemon=True)
        mock_thread.start.assert_called_once()


    @patch.object(AbstractSocketServer, "_create_socket")
    @patch("threading.Thread")
    def test_stop_server(self, mock_thread_class, mock_create_socket):
        """Test server stop"""
        mock_sock = Mock()
        mock_create_socket.return_value = mock_sock
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_thread_class.return_value = mock_thread
        server.start()
        server.stop()
        assert server.running is False
        mock_sock.close.assert_called_once()
        mock_thread.join.assert_called_once()


    def test_get_data_success(self):
        """Test successful data retrieval"""
        server.data_queue.put(b"test_data")
        data = server.get_data(timeout=0.1)
        assert data == b"test_data"


    def test_get_data_timeout(self):
        """Test data retrieval timeout"""
        data = server.get_data(timeout=0.01)
        assert data is None


    @patch.object(AbstractSocketServer, "_handle_client")
    def test_server_loop(self, mock_handle_client):
        """Test server main loop"""
        mock_sock = Mock()
        mock_client_sock = Mock()
        mock_sock.accept.side_effect = [
            (mock_client_sock, "client_addr"),
            socket.timeout,
            Exception("Server error")
        ]
        server.running = True
        server.server_socket = mock_sock
        server._server_loop()
        mock_sock.settimeout.assert_called_with(10)
        assert mock_handle_client.call_count == 1
        mock_handle_client.assert_called_once_with(mock_client_sock, "client_addr")