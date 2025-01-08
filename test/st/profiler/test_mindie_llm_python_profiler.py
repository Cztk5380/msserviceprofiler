# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

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
