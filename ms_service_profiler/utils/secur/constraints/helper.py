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
from dataclasses import dataclass

from .logic import FunctionConstraint, IfElseConstraint
from ._path import (
    IsFile, Exists, IsDir, HasSoftLink, IsReadable, 
    IsWritable, IsExecutable, IsWritableToGroupOrOthers, 
    IsConsistentToCurrentUser, IsSizeReasonable
)
from .base import BaseConstraint


class PathConstraintBuilder:
    """
    Constraint builder for IDE support.

    Available constraints:
        is_file, file_exists, is_dir, has_soft_link, is_readable, is_writable,
        is_executable, is_not_writable_to_group_or_others, is_consistent_to_current_user,
        is_size_reasonable
    """
    @staticmethod
    def is_file(): 
        return IsFile()
    
    @staticmethod
    def file_exists(): 
        return Exists()
    
    @staticmethod
    def is_dir(): 
        return IsDir()
    
    @staticmethod
    def has_soft_link(): 
        return HasSoftLink()
    
    @staticmethod
    def is_readable(): 
        return IsReadable()
    
    @staticmethod
    def is_writable(): 
        return IsWritable()
    
    @staticmethod
    def is_executable(): 
        return IsExecutable()
    
    @staticmethod
    def is_writable_to_group_or_others():
        return IsWritableToGroupOrOthers()
    
    @staticmethod
    def is_consistent_to_current_user():
        return IsConsistentToCurrentUser()
    
    @staticmethod
    def is_size_reasonable(*, size_limit=None, require_confirm=True):
        return IsSizeReasonable(size_limit=size_limit, require_confirm=require_confirm)


Path = PathConstraintBuilder


def make_constraint(constraint, description=None):
    if isinstance(constraint, BaseConstraint):
        return constraint

    if callable(constraint):
        return FunctionConstraint(constraint, description)

    raise TypeError(
        f"Expected a BaseConstraint instance or a callable, but got {type(constraint).__name__}."
    )


def where(condition, if_constraint, else_constraint, *, description=None):
    return IfElseConstraint(
        condition,
        make_constraint(if_constraint),
        make_constraint(else_constraint),
        description=description
    )


@dataclass(frozen=True)
class Rule:
    read_file_common_check: BaseConstraint = where(
        os.getuid() == 0, 
        Path.is_file(),
        Path.is_file() & ~Path.has_soft_link() & 
        Path.is_readable() & ~Path.is_writable_to_group_or_others() & 
        Path.is_consistent_to_current_user() & Path.is_size_reasonable(),
        description="current user is root"
    )

    exec_file_common_check: BaseConstraint = where(
        os.getuid() == 0, 
        Path.is_file(),
        Path.is_file() & ~Path.has_soft_link() & 
        Path.is_writable() & ~Path.is_writable_to_group_or_others() & 
        Path.is_consistent_to_current_user() & Path.is_size_reasonable(),
        description="current user is root"
    )
