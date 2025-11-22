# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import threading
from typing import Optional
from ms_service_profiler.utils.log import logger
from ms_service_profiler.tracer.binary_otlp_exporter import export_binary_data


class Scheduler:
    """Scheduler that periodically processes data from the socket server."""
    def __init__(self, interval: int, socket_server):
        """Initialize the scheduler."""
        self.interval = interval
        self.socket_server = socket_server
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def _run_task(self):
        """Run the export task."""
        if not self.running:
            return

        try:
            while True:
                data = self.socket_server.get_data()
                if not data:
                    break
                export_binary_data(data)
        except Exception as e:
            logger.warning(f"Export span failed: {str(e)}", exc_info=True)

        self.thread = threading.Timer(self.interval, self._run_task)
        self.thread.daemon = True
        self.thread.start()

    def start(self):
        """Start the scheduler."""
        if self.running:
            return
        self.running = True
        logger.info(f"Start scheduler task: interval {self.interval}s")
        self._run_task()

    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        self.running = False
        if self.thread:
            self.thread.cancel()
            self.thread.join(timeout=2)
        logger.info("Stop scheduler success.")