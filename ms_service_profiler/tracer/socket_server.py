# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import socket
import ctypes
import os
from typing import Optional
import queue
import threading
from ms_service_profiler.utils.log import logger


# Length field size for OTLP protocol
OTEL_Length_Field = 4


# define ucred
class Ucred(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint32),
        ("uid", ctypes.c_uint32),
        ("gid", ctypes.c_uint32)
    ]


class AbstractSocketServer:
    """Abstract socket server for receiving data."""
    def __init__(
        self,
        socket_name: str,
        buffer_size: int,
        max_listen_num: int,
        socket_timeout: int
    ):
        """Initialize the socket server."""
        self.socket_name = '\0' + socket_name # Use abstract namespace
        self.buffer_size = buffer_size
        self.max_listen_num = max_listen_num
        self.socket_timeout = socket_timeout
        self.data_queue = queue.Queue()
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None

    def _create_socket(self) -> socket.socket:
        """Create and bind the socket."""
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(self.socket_name)
            sock.listen(self.max_listen_num)
            logger.info(f"Start socket server success, listen addr: {self.socket_name}")
            return sock
        except Exception as e:
            if sock and sock.fileno() != -1:
                sock.close()
            logger.warning(f"Socket server {self.socket_name} create error: {str(e)}.", exc_info=True)
            raise

    @staticmethod
    def _validate_peer_cred(client_sock):
        cred = Ucred()
        cred_size = ctypes.sizeof(cred)

        try:
            # Get peer cred (SO_PEERCRED 17)
            cred_data = client_sock.getsockopt(socket.SOL_SOCKET, 17, cred_size)
            ctypes.memmove(ctypes.byref(cred), cred_data, cred_size)
        except Exception as e:
            print(f"Get peer cred failed: {e}")
            return False

        self_uid = os.getuid()
        peer_uid = cred.uid

        if peer_uid != self_uid:
            logger.debug(f"Current user {self_uid}, connect with unexpected user {cred.uid}.")
            return False

        return True

    def _handle_client(self, client_sock: socket.socket, client_addr, length_field_size=OTEL_Length_Field):
        """Handle a client connection."""
        try:
            logger.debug(f"New connection...")
            if not self._validate_peer_cred(client_sock):
                logger.warning(f"Unexpected connection.")
                return

            buffer = self._handle_recv(client_sock, length_field_size)
            if buffer:
                logger.warning(f"Data remaining in buffer: {len(buffer)} bytes.")
        except Exception as e:
            logger.warning(f"Socket server handle error: {str(e)}.", exc_info=True)

    def _handle_recv(self, client_sock, length_field_size):
        buffer = bytearray()
        while True:
            chunk = client_sock.recv(self.buffer_size)
            if not chunk:
                break
            buffer.extend(chunk)

            # Process data frames
            while len(buffer) >= length_field_size:
                length = int.from_bytes(buffer[:length_field_size], byteorder='big')
                if len(buffer) >= length_field_size + length:
                    data = buffer[length_field_size:length_field_size + length]
                    buffer = buffer[length_field_size + length:]
                    logger.debug(f"Receive data: {len(data)} bytes.")
                    self.data_queue.put(data)
                else:
                    break
        return buffer

    def _server_loop(self):
        """Main server loop."""
        while self.running:
            try:
                self.server_socket.settimeout(self.socket_timeout)
                client_sock, client_addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.warning(f"Socket server error: {str(e)}.", exc_info=True)
                break

    def start(self):
        """Start the socket server."""
        if self.running:
            return
        self.running = True
        self.server_socket = self._create_socket()
        self.thread = threading.Thread(target=self._server_loop, daemon=True)
        self.thread.start()

    def get_data(self, timeout=0.5) -> Optional[bytes]:
        """Get data from the queue."""
        try:
            return self.data_queue.get(block=False, timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """Stop the socket server."""
        if not self.running:
            return
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.thread and self.thread.is_alive():
            self.thread.join()
        logger.info("Stop socket success.")