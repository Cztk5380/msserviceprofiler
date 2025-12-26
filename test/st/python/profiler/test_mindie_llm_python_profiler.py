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

import warnings
from unittest import TestCase


class TestMindIELLMPytonProf(TestCase):
    def test_mindie_llm_prof(self):
        try:
            from mindie_llm.utils.prof.profiler import span_start, span_end, span_req
        except ImportError:
            warnings.warn(UserWarning("cannot import mindie_llm, skip this test"))
            return

        prof = span_start("test")
        self.assertIsNotNone(prof)
        prof = span_req(prof, [1, 2, 3])
        self.assertIsNotNone(prof)
        span_end(prof)

        self.assertIsNone(span_start())
        self.assertIsNone(span_end())
        self.assertIsNone(span_end(None))
        self.assertIsNone(span_req())
        self.assertIsNone(span_req(None))
