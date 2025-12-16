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

import os

from ..constraints import PathConstraint, Rule, InvalidParameterError


def update_env_s(
        env_var: str,
        path: str,
        constraint: PathConstraint = Rule.input_file_read,
        prepend: bool = True
    ) -> None:
    """
    Add a path to an environment variable for searching.

    Parameters
    ----------
    env_var : str
        The name of the environment variable to modify.
    path : str
        The directory path to add to the environment variable.
    prepend : bool, optional
        If True, add the path to the beginning of the variable. If False, add to the end.
        Default is True.

    Raises
    ------
    TypeError
        If `env_var` is not a string.

    Notes
    -----
    If the environment variable does not exist, it will be created with the given path.
    If `path` is not absolute, it will be converted to an absolute path.
    """
    if not isinstance(env_var, str):
        raise TypeError(
            f"Expected 'env_var' to be str. Got {type(env_var).__name__} instead."
        )

    abs_path = os.path.abspath(path)
    if not constraint.is_satisfied_by(abs_path):
        raise InvalidParameterError("env_var", "update_env_s", constraint, abs_path)

    current_value = os.environ.get(env_var)

    if current_value:
        parts = [p for p in current_value.split(os.pathsep)]
        if prepend:
            parts.insert(0, abs_path)
        else:
            parts.append(abs_path)
        new_value = os.pathsep.join(parts)
    else:
        new_value = abs_path

    os.environ[env_var] = new_value
