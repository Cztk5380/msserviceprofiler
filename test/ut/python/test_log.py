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