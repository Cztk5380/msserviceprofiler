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

import argparse
from functools import wraps

from ..constraints import BaseConstraint, InvalidParameterError
from .decorator_usage import validate_params


def validate_args(constraint: BaseConstraint, *, fall_back_fn=None):
    """
    Usage: parser.add_argument("xx", type=validate_args(xxx))

    pass the `wrapper` to argparse, pass `arg` to `arg_check`and catch the error msg
    """
    def arg_check(arg: str):
        if not constraint.is_satisfied_by(arg):
            invalid_param_error = InvalidParameterError(
                'arg', arg_check.__qualname__,
                constraint, arg
            )
            error_msg = invalid_param_error.build_error_message()

            if not fall_back_fn:
                raise argparse.ArgumentTypeError(error_msg)
            
            fall_back_fn(arg)
        return arg

    @wraps(arg_check)
    def wrapper(arg):
        return arg_check(arg)

    return wrapper
