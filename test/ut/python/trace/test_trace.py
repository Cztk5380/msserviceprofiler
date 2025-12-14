# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

from unittest.mock import patch, MagicMock
from ms_service_profiler.trace import main


class TestMain:
    @patch('ms_service_profiler.trace.argparse.ArgumentParser')
    @patch('ms_service_profiler.trace.set_log_level')
    @patch('ms_service_profiler.trace.OTLPForwarderService')
    def test_main_success(self, mock_otlp_service, mock_set_log_level, mock_arg_parser):
        """Test the behavior of the main function in a successful scenario"""
        mock_args = MagicMock()
        mock_args.log_level = 'info'
        mock_arg_parser.return_value.parse_args.return_value = mock_args
        mock_service_instance = MagicMock()
        mock_otlp_service.return_value = mock_service_instance
        main()
        mock_set_log_level.assert_called_once_with('info')
        mock_service_instance.start.assert_called_once()