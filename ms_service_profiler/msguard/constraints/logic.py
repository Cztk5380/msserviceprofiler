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

import inspect
from abc import abstractmethod

from .base import BaseConstraint, ConstraintStatus
from ..utils import GlobalConfig


class LogicConstraint(BaseConstraint):
    @abstractmethod
    def _is_satisfied_by(self, val):
        pass

    def is_satisfied_by(self, val):
        if GlobalConfig.is_custom_set():
            return GlobalConfig.custom_return

        ret = self._is_satisfied_by(val)
        self.status = ConstraintStatus.SUCCESS if ret else ConstraintStatus.FAILURE
        return ret


class NullConstraint(LogicConstraint):
    def __init__(self, *, description=None):
        description = "always true" if description is None else description
        super().__init__(description=description)

    def _is_satisfied_by(self, val):
        return True


class FunctionConstraint(LogicConstraint):
    def __init__(self, func, description=None):
        super().__init__(description=description)

        # Check if the function has exactly one parameter
        sig = inspect.signature(func)
        if len(sig.parameters) != 1:
            raise ValueError(f"The function {func.__qualname__} must have exactly one parameter.")

        self.func = func
        self.description = description or func.__qualname__

    def _is_satisfied_by(self, val):
        result = self.func(val)

        if not isinstance(result, bool):
            raise TypeError(
                f"Expected 'result' to be bool. Got {type(result).__name__} instead."
            )
        return result


class AndConstraint(LogicConstraint):
    def __init__(self, *constraints, description=None):
        self.constraints = constraints
        description = " and ".join(c.description for c in self.constraints)
        super().__init__(description=description)

    def __str__(self):
        for constraint in self.constraints:
            if constraint.status == ConstraintStatus.FAILURE:
                return str(constraint)
        return self.description

    def _is_satisfied_by(self, val):
        return all(c.is_satisfied_by(val) for c in self.constraints)


class OrConstraint(LogicConstraint):
    def __init__(self, *constraints, description=None):
        self.constraints = constraints
        description = " or ".join(c.description for c in self.constraints)
        super().__init__(description=description)
        
    def __str__(self):
        for constraint in self.constraints:
            if constraint.status == ConstraintStatus.FAILURE:
                return str(constraint)
        return self.description

    def _is_satisfied_by(self, val):
        return any(c.is_satisfied_by(val) for c in self.constraints)
    
    
class NotConstraint(LogicConstraint):
    def __init__(self, constraint, *, description=None):
        self.constraint = constraint
        description = f"not {self.constraint.description}"
        super().__init__(description=description)

    def _is_satisfied_by(self, val):
        return not self.constraint.is_satisfied_by(val)


class IfElseConstraint(LogicConstraint):
    def __init__(self, condition, if_constraint, else_constraint, *, description=None):
        super().__init__(description=description)

        self.condition = make_constraint(condition, description)
        self.if_constraint = if_constraint
        self.else_constraint = else_constraint
        self.condition_res = False
    
    def __str__(self):
        return f"{self.if_constraint if self.condition_res else self.else_constraint}"

    def _is_satisfied_by(self, val):
        self.condition_res = self.condition.is_satisfied_by(val)
        return self.if_constraint.is_satisfied_by(val) if \
               self.condition_res else \
               self.else_constraint.is_satisfied_by(val)


def make_constraint(constraint, description=None) -> BaseConstraint:
    """Convert None, bool, function and constraint to constraint"""
    if constraint is None:
        return NullConstraint()

    if isinstance(constraint, BaseConstraint):
        return constraint
    
    if isinstance(constraint, bool):
        if description is None:
            raise ValueError("'description' must not be None when 'condition' is bool")

        return FunctionConstraint(lambda _: constraint, description)

    if callable(constraint):
        return FunctionConstraint(constraint, description)

    raise TypeError(
        f"Expected 'constraint' to be BaseContraint, bool, or Callable. "
        f"Got {type(constraint).__name__} instead."
    )


def where(condition, if_constraint, else_constraint, *, description=None):
    """description is used for 'condition'"""
    return IfElseConstraint(
        condition,
        if_constraint,
        else_constraint,
        description=description
    )
