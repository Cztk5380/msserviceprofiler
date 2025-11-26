# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import signal
import queue
from ms_service_profiler.utils.log import logger
from ms_service_profiler.tracer.socket_server import AbstractSocketServer
from ms_service_profiler.tracer.binary_otlp_exporter import check_export_initialization
from ms_service_profiler.tracer.scheduler import Scheduler


# Constants for socket server configuration
SOCKET_NAME = "OTLP_SOCKET"
SOCKET_BUFFER_SIZE = 4096
SOCKET_TIMEOUT = 1
MAX_LISTEN_NUM = 8
MAX_QUEUE_SIZE = 1000000
WARNING_QUEUE_SIZE = 100000

# Constants for scheduler configuration
INTERVAL_SECONDS = 1


class OTLPForwarderService:
    """OTLP Forwarder Service that listens for data and forwards it to an OTLP receiver."""
    def __init__(self):
        """Initialize the OTLP Forwarder Service."""
        self.signal_queue = queue.Queue()
        if not check_export_initialization():
            raise Exception("Initialize OTLP exporter error.")

        self.socket_server = AbstractSocketServer(
            socket_name=SOCKET_NAME,
            buffer_size=SOCKET_BUFFER_SIZE,
            max_listen_num=MAX_LISTEN_NUM,
            socket_timeout=SOCKET_TIMEOUT,
            max_queue_size=MAX_QUEUE_SIZE,
            warning_queue_size=WARNING_QUEUE_SIZE
        )
        self.scheduler = Scheduler(
            interval=INTERVAL_SECONDS,
            socket_server=self.socket_server
        )

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Receive signal {signum}, quit...")
        self.stop()
        self.signal_queue.put("0")

    def start(self):
        """Start the OTLP Forwarder Service."""
        try:
            self.socket_server.start()
            self.scheduler.start()
            logger.info("Start OTLPForwarderService success, running...")
            while self.signal_queue.empty():
                if self.signal_queue.get():
                    break
        except KeyboardInterrupt:
            logger.info(f"Receive KeyboardInterrupt, quit...")
            self.stop()
        except Exception as e:
            logger.warning(f"Unexpected error occurred: {e}, quit...")
            self.stop()

    def stop(self):
        """Stop the OTLP Forwarder Service."""
        self.scheduler.stop()
        self.socket_server.stop()
        logger.info("Stop OTLPForwarderService success.")