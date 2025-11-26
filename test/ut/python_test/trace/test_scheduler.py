# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import Mock, patch
from ms_service_profiler.tracer.scheduler import Scheduler


class TestScheduler(unittest.TestCase):
    def setUp(self):
        """Initialize mock dependencies before tests."""
        self.mock_socket_server = Mock()
        self.scheduler = Scheduler(interval=1, socket_server=self.mock_socket_server)

    def tearDown(self):
        """Clean up resources after tests."""
        if self.scheduler.running:
            self.scheduler.stop()

    def test_init(self):
        """Test if initialization parameters are correct."""
        self.assertEqual(self.scheduler.interval, 1)
        self.assertEqual(self.scheduler.socket_server, self.mock_socket_server)
        self.assertFalse(self.scheduler.running)
        self.assertIsNone(self.scheduler.thread)
        self.assertTrue(self.scheduler.waiting_queue.empty())
        self.assertEqual(self.scheduler.retry_intervals, [30, 60, 120, 240, 480, 960, 1800])
        self.assertEqual(self.scheduler.current_retry_index, 0)

    @patch('ms_service_profiler.tracer.scheduler.export_binary_data')
    @patch('ms_service_profiler.tracer.scheduler.time.sleep')  # Mock sleep to avoid actual waiting
    def test_heart_beat_connect_success(self, mock_sleep, mock_export):
        """Test _heart_beat_connect succeeds after retries."""
        mock_export.side_effect = [False, True]
        self.scheduler.waiting_queue.put("0")
        self.scheduler._heart_beat_connect(b"test_data")
        self.assertEqual(self.scheduler.current_retry_index, 0)
        self.assertTrue(self.scheduler.waiting_queue.empty())

    def test_start_and_stop(self):
        """Test if start and stop methods correctly control the running state."""
        with patch.object(self.scheduler, '_run_task') as mock_run:
            self.scheduler.start()
            self.assertTrue(self.scheduler.running)
            mock_run.assert_called_once()

            self.scheduler.stop()
            self.assertFalse(self.scheduler.running)