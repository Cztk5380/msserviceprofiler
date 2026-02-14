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

from ms_service_profiler.utils.expr_eval import ExprEval


class TestExprEval(unittest.TestCase):

    def test_expr_eval(self):
        class ObjCase:
            def __init__(self):
                self.waiting = 2

        a = 113
        b = 100
        dict_case = {"a": 1, "b": 3}
        list_case = [1, 2]
        obj_case = ObjCase()
        expr_eval = ExprEval(
            "-a + b*2 / (len(list_case) + obj_case.waiting + int(20.0) + "
            "float(30) + list_case[1] + dict_case['a'] + 10)"
        )
        expr_eval.register_function("str", str)
        res = expr_eval({"a": a, "b": b, "dict_case": dict_case, "list_case": list_case, "obj_case": obj_case})
        self.assertEqual(-a + b*2 / (len(list_case) + obj_case.waiting + int(20.0) +
                                     float(30) + list_case[1] + dict_case['a'] + 10), res)

        expr_eval = ExprEval("str(a)")
        res = expr_eval({"a": a})
        self.assertEqual(str(a), res)
