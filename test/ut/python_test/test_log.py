# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import unittest
import logging
from unittest.mock import MagicMock
from ms_service_profiler.utils.log import logger, set_log_level, set_logger


class TestLogger(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)

    def test_set_log_level_valid(self):
        # 测试设置有效日志级别
        set_log_level('debug')
        self.assertEqual(logger.level, logging.DEBUG)

    def test_set_log_level_invalid(self):
        # 测试设置无效日志级别
        set_log_level('invalid_level')
        self.assertEqual(logger.level, logging.INFO)

    def test_set_logger(self):
        set_logger(self.logger)
        self.assertEqual(len(self.logger.handlers), 1)
        self.assertIsInstance(self.logger.handlers[0], logging.StreamHandler)


if __name__ == '__main__':
    unittest.main()