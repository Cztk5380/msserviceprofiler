# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
