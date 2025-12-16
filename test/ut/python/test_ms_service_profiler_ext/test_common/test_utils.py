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
from unittest.mock import patch
import pandas as pd

from ms_service_profiler.ms_service_profiler_ext.common.utils import confirmation_interaction


class TestUtilsFuctions(unittest.TestCase):
    @patch('builtins.input', return_value='yes')
    def test_confirmation_interaction_true(self, mock_input):
        prompt = "(y/n): "
        result = confirmation_interaction(prompt)
        self.assertTrue(result)
    
    @patch('builtins.input', side_effect=Exception)
    def test_confirmation_interaction_exception(self, mock_input):
        prompt = "(y/n): "
        result = confirmation_interaction(prompt)
        self.assertFalse(result)
    