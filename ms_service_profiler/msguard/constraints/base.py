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

from enum import Enum, auto
from abc import ABC, abstractmethod


class ConstraintStatus(Enum):
    SUCCESS = auto()
    FAILURE = auto()
    SKIPPED = auto()
    

class BaseConstraint(ABC):
    def __init__(self, *, description=None):
        self.description = "" if description is None else description 
        self.status = ConstraintStatus.SKIPPED

    def __str__(self):
        return self.description

    def __and__(self, other):
        from .logic import AndConstraint, make_constraint
        return AndConstraint(self, make_constraint(other))

    def __or__(self, other):
        from .logic import OrConstraint, make_constraint
        return OrConstraint(self, make_constraint(other))

    def __invert__(self):
        from .logic import NotConstraint
        return NotConstraint(self)

    @abstractmethod
    def is_satisfied_by(self, val):
        pass
