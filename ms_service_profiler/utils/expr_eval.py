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
import ast
import operator
import math


class ExprEval:
    """
    parse and evaluate expression
    """
    OPERATOR = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
    }

    FUNCTION = {
        'abs': abs,
        'round': round,
        'len': len,
        'int': int,
        'float': float,
        'str': str,
        'max': max,
        'min': min,
        'pow': pow,
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'exp': math.exp,
        'ceil': math.ceil,
        'floor': math.floor,
    }

    def __init__(self, expression):
        self.params = {}
        self.visitor = {
            ast.Num: self._visit_num,
            ast.Constant: self._visit_constant,
            ast.Name: self._visit_name,
            ast.Call: self._visit_call,
            ast.Attribute: self._visit_attribute,
            ast.Subscript: self._visit_subscript,
            ast.UnaryOp: self._visit_unary_op,
            ast.BinOp: self._visit_bin_op,
        }
        # parse expression
        self.expr = ast.parse(expression, mode='eval')

    def __call__(self, params, *args, **kwargs):
        # update params
        self.params.update(params)

        # evaluate expression
        return self._evaluate(self.expr.body)

    @staticmethod
    def _visit_num(node):
        return node.n

    @staticmethod
    def _visit_constant(node):
        return node.value

    def _visit_name(self, node):
        if node.id not in self.params:
            raise NameError(f"Undefined params: {node.id}")
        return self.params[node.id]

    def _visit_call(self, node):
        func = self.FUNCTION.get(node.func.id)
        if func is None:
            raise NameError(f"Undefined function: {node.func.id}")
        args = [self._evaluate(arg) for arg in node.args]
        kwargs = {keywords.arg: self._evaluate(keywords.value) for keywords in node.keywords}
        return func(*args, **kwargs)

    def _visit_attribute(self, node):
        return getattr(self._evaluate(node.value), node.attr)

    def _visit_subscript(self, node):
        container = self._evaluate(node.value)
        key = self._evaluate(node.slice)
        if isinstance(container, list) and len(container) <= key:
            raise Exception(f"len of list {container} <= {key}")
        if isinstance(container, dict) and key not in container:
            raise Exception(f"{key} not in dict {container}")
        return container[key]

    def _visit_unary_op(self, node):
        unary_op = self.get_operator(node)
        return unary_op(self._evaluate(node.operand))

    def _visit_bin_op(self, node):
        bin_op = self.get_operator(node)
        return bin_op(self._evaluate(node.left), self._evaluate(node.right))

    def _evaluate(self, node):
        if type(node) not in self.visitor:
            raise TypeError(f"Unsupported type: {type(node)}")

        return self.visitor[type(node)](node)

    def register_function(self, name, func):
        self.FUNCTION.update({name: func})

    def get_operator(self, node):
        if type(node.op) not in self.OPERATOR:
            raise NameError(f"Undefined operator: {type(node.op)}")
        return self.OPERATOR[type(node.op)]
