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
"""
ExprEval - 表达式求值器

支持安全的数学表达式求值，可用于配置中的表达式计算。
支持变量、函数调用、属性访问、下标访问等操作。
"""

import ast
import math
import operator
from typing import Any, Callable, Dict, Optional


class ExprEval:
    """表达式求值器
    
    解析并求值数学表达式，支持以下特性：
    - 基本数学运算: +, -, *, /, //, %, **
    - 变量引用: 从params中获取变量值
    - 函数调用: abs, round, len, max, min等
    - 属性访问: obj.attr
    - 下标访问: list[index], dict[key]
    
    示例:
        evaluator = ExprEval("x + y * 2")
        result = evaluator({"x": 10, "y": 5})  # 返回 20
        
        evaluator = ExprEval("len(items) + sqrt(value)")
        result = evaluator({"items": [1, 2, 3], "value": 16})  # 返回 7
    
    Attributes:
        OPERATOR: 支持的运算符映射
        FUNCTION: 支持的内置函数映射
    """
    
    # 支持的运算符
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
    
    # 支持的内置函数
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
    
    def __init__(self, expression: str):
        """初始化表达式求值器
        
        Args:
            expression: 表达式字符串
            
        Raises:
            SyntaxError: 如果表达式语法错误
        """
        self._params: Dict[str, Any] = {}
        # 创建实例级别的函数字典，复制类属性以避免共享状态
        self._functions: Dict[str, Callable] = dict(self.FUNCTION)
        self._operators: Dict[type, Callable] = dict(self.OPERATOR)
        self._visitor: Dict[type, Callable] = {
            ast.Num: self._visit_num,
            ast.Constant: self._visit_constant,
            ast.Name: self._visit_name,
            ast.Call: self._visit_call,
            ast.Attribute: self._visit_attribute,
            ast.Subscript: self._visit_subscript,
            ast.UnaryOp: self._visit_unary_op,
            ast.BinOp: self._visit_bin_op,
        }
        
        # 解析表达式
        try:
            self._expr = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            raise SyntaxError(f"Invalid expression syntax: {expression}") from e
    
    def __call__(self, params: Dict[str, Any], *args, **kwargs) -> Any:
        """求值表达式
        
        Args:
            params: 变量名到值的映射字典
            *args: 额外位置参数（未使用）
            **kwargs: 额外关键字参数（未使用）
            
        Returns:
            表达式求值结果
            
        Raises:
            NameError: 如果引用了未定义的变量或函数
            TypeError: 如果使用了不支持的节点类型
        """
        # 更新参数
        self._params = dict(params)
        
        # 求值表达式
        return self._evaluate(self._expr.body)
    
    @staticmethod
    def _visit_num(node: ast.Num) -> Any:
        """访问数字节点（Python < 3.8）"""
        return node.n
    
    @staticmethod
    def _visit_constant(node: ast.Constant) -> Any:
        """访问常量节点（Python >= 3.8）"""
        return node.value
    
    def _visit_name(self, node: ast.Name) -> Any:
        """访问变量名节点
        
        从params中获取变量值。
        
        Args:
            node: Name节点
            
        Returns:
            变量值
            
        Raises:
            NameError: 如果变量未定义
        """
        if node.id not in self._params:
            raise NameError(f"Undefined variable: {node.id}")
        return self._params[node.id]
    
    def _visit_call(self, node: ast.Call) -> Any:
        """访问函数调用节点
        
        Args:
            node: Call节点
            
        Returns:
            函数调用结果
            
        Raises:
            NameError: 如果函数未定义
        """
        # 获取函数名
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # 处理方法调用，如 math.sqrt
            func_name = node.func.attr
        else:
            raise NameError(f"Unsupported function call: {ast.dump(node.func)}")
        
        func = self._functions.get(func_name)
        if func is None:
            raise NameError(f"Undefined function: {func_name}")
        
        # 求值参数
        args = [self._evaluate(arg) for arg in node.args]
        kwargs = {
            keyword.arg: self._evaluate(keyword.value)
            for keyword in node.keywords
        }
        
        return func(*args, **kwargs)
    
    def _visit_attribute(self, node: ast.Attribute) -> Any:
        """访问属性访问节点
        
        例如: obj.attr
        
        Args:
            node: Attribute节点
            
        Returns:
            属性值
        """
        obj = self._evaluate(node.value)
        return getattr(obj, node.attr)
    
    def _visit_subscript(self, node: ast.Subscript) -> Any:
        """访问下标访问节点
        
        例如: list[index], dict[key]
        
        Args:
            node: Subscript节点
            
        Returns:
            下标访问结果
            
        Raises:
            Exception: 如果下标越界或键不存在
        """
        container = self._evaluate(node.value)
        
        # 处理不同Python版本的slice
        if isinstance(node.slice, ast.Index):
            # Python < 3.9
            key = self._evaluate(node.slice.value)
        else:
            # Python >= 3.9
            key = self._evaluate(node.slice)
        
        # 检查边界
        if isinstance(container, list) and isinstance(key, int):
            if key < 0:
                key = len(container) + key
            if key < 0 or key >= len(container):
                raise IndexError(f"List index out of range: {key} (len={len(container)})")
        
        if isinstance(container, dict) and key not in container:
            raise KeyError(f"Key not found in dict: {key}")
        
        return container[key]
    
    def _visit_unary_op(self, node: ast.UnaryOp) -> Any:
        """访问一元运算符节点
        
        例如: -x, +x
        
        Args:
            node: UnaryOp节点
            
        Returns:
            运算结果
        """
        unary_op = self._get_operator(node)
        return unary_op(self._evaluate(node.operand))
    
    def _visit_bin_op(self, node: ast.BinOp) -> Any:
        """访问二元运算符节点
        
        例如: x + y, x * y
        
        Args:
            node: BinOp节点
            
        Returns:
            运算结果
        """
        bin_op = self._get_operator(node)
        return bin_op(
            self._evaluate(node.left),
            self._evaluate(node.right)
        )
    
    def _evaluate(self, node: ast.AST) -> Any:
        """递归求值AST节点
        
        Args:
            node: AST节点
            
        Returns:
            节点求值结果
            
        Raises:
            TypeError: 如果节点类型不支持
        """
        node_type = type(node)
        if node_type not in self._visitor:
            raise TypeError(f"Unsupported AST node type: {node_type}")
        
        return self._visitor[node_type](node)
    
    def register_function(self, name: str, func: Callable):
        """注册自定义函数
        
        Args:
            name: 函数名
            func: 函数对象
        """
        self._functions[name] = func
    
    def _get_operator(self, node: ast.AST) -> Callable:
        """获取运算符对应的函数
        
        Args:
            node: 包含op属性的AST节点
            
        Returns:
            运算符函数
            
        Raises:
            NameError: 如果运算符不支持
        """
        op_type = type(node.op)
        if op_type not in self._operators:
            raise NameError(f"Undefined operator: {op_type}")
        return self._operators[op_type]


def evaluate_expression(expression: str, params: Dict[str, Any]) -> Any:
    """便捷函数：求值表达式
    
    Args:
        expression: 表达式字符串
        params: 变量名到值的映射字典
        
    Returns:
        表达式求值结果
        
    Example:
        >>> result = evaluate_expression("x + y", {"x": 10, "y": 20})
        >>> print(result)  # 30
    """
    evaluator = ExprEval(expression)
    return evaluator(params)
