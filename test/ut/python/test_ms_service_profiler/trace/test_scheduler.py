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
    @patch('ms_service_profiler.tracer.scheduler.time.sleep')
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

    @patch('ms_service_profiler.tracer.scheduler.export_binary_data')
    @patch('ms_service_profiler.tracer.scheduler.threading.Timer')
    def test_run_task_when_not_running(self, mock_timer, mock_export):
        """Test _run_task returns immediately when not running."""
        self.scheduler.running = False
        self.scheduler._run_task()

        mock_timer.assert_not_called()
        self.mock_socket_server.get_data.assert_not_called()
        mock_export.assert_not_called()

    @patch('ms_service_profiler.tracer.scheduler.export_binary_data')
    @patch('ms_service_profiler.tracer.scheduler.threading.Timer')
    def test_run_task_with_no_data(self, mock_timer, mock_export):
        """Test _run_task with no data available."""
        self.scheduler.running = True
        self.mock_socket_server.get_data.return_value = None

        mock_timer_instance = Mock()
        mock_timer.return_value = mock_timer_instance

        self.scheduler._run_task()

        self.mock_socket_server.get_data.assert_called_once()
        mock_export.assert_not_called()
        mock_timer.assert_called_once_with(1, self.scheduler._run_task)
        mock_timer_instance.start.assert_called_once()

    @unittest.skip
    @patch('ms_service_profiler.tracer.scheduler.export_binary_data')
    @patch('ms_service_profiler.tracer.scheduler.threading.Timer')
    def test_run_task_successful_export(self, mock_timer, mock_export):
        """Test _run_task with successful data export."""
        self.scheduler.running = True
        test_data = b"test_data"
        self.mock_socket_server.get_data.return_value = test_data
        mock_export.return_value = True

        mock_timer_instance = Mock()
        mock_timer.return_value = mock_timer_instance

        self.scheduler._run_task()

        self.mock_socket_server.get_data.assert_called_once()
        mock_export.assert_called_once_with(test_data)
        self.assertTrue(self.scheduler.waiting_queue.empty())
        mock_timer.assert_called_once_with(1, self.scheduler._run_task)

    @patch('ms_service_profiler.tracer.scheduler.export_binary_data')
    @patch('ms_service_profiler.tracer.scheduler.threading.Timer')
    def test_run_task_export_failure(self, mock_timer, mock_export):
        """Test _run_task with export failure triggering retry logic."""
        self.scheduler.running = True
        test_data = b"test_data"
        self.mock_socket_server.get_data.return_value = test_data
        mock_export.return_value = False

        mock_timer_instance = Mock()
        mock_timer.return_value = mock_timer_instance

        with patch.object(self.scheduler, '_heart_beat_connect') as mock_heartbeat:
            self.scheduler._run_task()

            self.mock_socket_server.get_data.assert_called_once()
            mock_export.assert_called_once_with(test_data)
            self.assertFalse(self.scheduler.waiting_queue.empty())
            mock_heartbeat.assert_called_once_with(test_data)
            mock_timer.assert_called_once_with(1, self.scheduler._run_task)

    @patch('ms_service_profiler.tracer.scheduler.export_binary_data')
    @patch('ms_service_profiler.tracer.scheduler.threading.Timer')
    @patch('ms_service_profiler.tracer.scheduler.logger')
    def test_run_task_exception_handling(self, mock_logger, mock_timer, mock_export):
        """Test _run_task exception handling."""
        self.scheduler.running = True
        self.mock_socket_server.get_data.side_effect = Exception("Test exception")

        mock_timer_instance = Mock()
        mock_timer.return_value = mock_timer_instance

        self.scheduler._run_task()

        mock_logger.warning.assert_called_once()
        mock_timer.assert_called_once_with(1, self.scheduler._run_task)

    @patch('ms_service_profiler.tracer.scheduler.export_binary_data')
    @patch('ms_service_profiler.tracer.scheduler.threading.Timer')
    def test_run_task_with_existing_waiting_queue(self, mock_timer, mock_export):
        """Test _run_task when waiting queue is not empty."""
        self.scheduler.running = True
        self.scheduler.waiting_queue.put("pending_data")

        mock_timer_instance = Mock()
        mock_timer.return_value = mock_timer_instance

        self.scheduler._run_task()

        self.mock_socket_server.get_data.assert_not_called()
        mock_export.assert_not_called()
        mock_timer.assert_called_once_with(1, self.scheduler._run_task)