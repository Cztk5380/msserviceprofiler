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
import functools

from .constraints import InvalidParameterError, make_constraint


def validate_parameter_constraint(parameter_constraint, params, caller_name):
    for param_name, param_val in params.items():
        if param_name not in parameter_constraint:
            continue

        constraint = parameter_constraint[param_name]

        if constraint == "no_validation":
            continue
        
        # support func | \ & constraint, constraint | \ & func
        constraint = make_constraint(constraint)

        if not constraint.is_satisfied_by(param_val):
            raise InvalidParameterError(
                f"The parameter '\033[0;31m{param_name!r}\033[0m' of '\033[0;31m{caller_name!r}\033[0m' "
                f"must satisfy the following requirement:\n\t \033[0;33m{constraint}\033[0m.\n"
                f"Got \033[0;31m{param_val!r}\033[0m instead."
            )


def validate_params(parameter_constraint):

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_sig = inspect.signature(func)

            params = func_sig.bind(*args, **kwargs)
            params.apply_defaults()

            ignore_params = [
                p.name
                for p in func_sig.parameters.values()
                if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
            ] + ["self", "cls"]
            params = {k: v for k, v in params.arguments.items() if k not in ignore_params}

            validate_parameter_constraint(
                parameter_constraint, params, caller_name=func.__qualname__
            )

            return func(*args, **kwargs)
        return wrapper

    return decorator
