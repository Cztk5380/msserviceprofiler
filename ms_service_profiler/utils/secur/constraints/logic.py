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

from .base import BaseConstraint


class FunctionConstraint(BaseConstraint):
    def __init__(self, func, description=None):
        super().__init__(description=description)
        # Check if the function has exactly one parameter
        sig = inspect.signature(func)

        if len(sig.parameters) != 1:
            raise ValueError(f"The function {func.__qualname__} must have exactly one parameter.")

        self.func = func
        self.description = description or func.__name__
        
    def __str__(self):
        return self.description

    def is_satisfied_by(self, val):
        result = self.func(val)

        if not isinstance(result, bool):
            raise TypeError("The function must return a boolean value.")
        return result


class AndConstraint(BaseConstraint):
    def __init__(self, *constraints, description=None):
        super().__init__(description=description)

        self.constraints = constraints
        self.description = " and ".join(str(c) for c in constraints)

    def is_satisfied_by(self, val):
        return all(c.is_satisfied_by(val) for c in self.constraints)


class OrConstraint(BaseConstraint):
    def __init__(self, *constraints, description=None):
        super().__init__(description=description)
        
        self.constraints = constraints
        self.description = " or ".join(str(c) for c in constraints)

    def is_satisfied_by(self, val):
        return any(c.is_satisfied_by(val) for c in self.constraints)
    
    
class NotConstraint(BaseConstraint):
    def __init__(self, constraint, *, description=None):
        super().__init__(description=description)
        
        self.constraint = constraint
        self.description = f"not {self.constraint}"

    def is_satisfied_by(self, val):
        return not self.constraint.is_satisfied_by(val)


class IfElseConstraint(BaseConstraint):
    def __init__(self, condition, if_constraint, else_constraint, *, description=None):
        super().__init__(description=description)
        
        if isinstance(condition, bool):
            if description is None:
                raise ValueError("'description' must not be None when 'condition' is a function")
            self.condition = FunctionConstraint(lambda _: condition, description)
        elif isinstance(condition, BaseConstraint):
            self.condition = condition  
        else:
            raise TypeError(f"'condition' must be bool or BaseConstraint. Got {type(condition).__name__} instead")

        self.if_constraint = if_constraint
        self.else_constraint = else_constraint
        self.description = f"if {self.condition.description}, then {if_constraint}. Otherwise {else_constraint}"

    def is_satisfied_by(self, val):
        if self.condition.is_satisfied_by(val):
            return self.if_constraint.is_satisfied_by(val)
        else:
            return self.else_constraint.is_satisfied_by(val)
