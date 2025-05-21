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

import os
from abc import ABC, abstractmethod


class InvalidParameterError(Exception):
    pass


class BaseConstraint(ABC):
    description = ""
    
    def __init__(self, *, description=None):
        self.description = self.description if description is None else description

    def __str__(self):
        return self.description
    
    def __and__(self, other):
        from .logic import AndConstraint
        from .helper import make_constraint 
        
        return AndConstraint(self, make_constraint(other))

    def __or__(self, other):
        from .logic import OrConstraint
        from .helper import make_constraint   
        
        return OrConstraint(self, make_constraint(other))
    
    def __invert__(self):
        from .logic import NotConstraint
        return NotConstraint(self)
    
    def __call__(self, val):
        return self.is_satisfied_by(val)

    @abstractmethod
    def is_satisfied_by(self, val):
        pass
    

class BasePathConstraint(BaseConstraint):
    def __init__(self, *, description=None):
        super().__init__(description=description)
        
    def __str__(self):
        return self.description
        
    def _get_path_stat(self, path: str):
        st = None
        # does not support file descriptor
        if not isinstance(path, (str, os.PathLike)):
            return st
        
        try:
            st = os.stat(path, follow_symlinks=False)
        except OSError:
            pass
        return st
