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


class InvalidParameterError(Exception):
    # Class-level constants for colors (only computed once)
    _COLORS = {
        'RED': "\033[1;31m",
        'YELLOW': "\033[1;33m",
        'CYAN': "\033[1;36m",
        'RESET': "\033[0m"
    }

    def __init__(self, parameter_name, caller_name, constraint, parameter_value):
        self.parameter_name = parameter_name
        self.caller_name = caller_name
        self.constraint = constraint
        self.parameter_value = parameter_value

        super().__init__(self.build_error_message())

    def build_error_message(self):
        """Build the complete error message with colors and formatting"""
        message = f"Parameter validation failed in " \
                  f"{self._COLORS['CYAN']}function {self.caller_name!r}{self._COLORS['RESET']}: " \
                  f"{self._COLORS['YELLOW']}expected parameter {self.parameter_name!r} " \
                  f"{self.constraint}{self._COLORS['RESET']}, " \
                  f"{self._COLORS['RED']}but receieved {self.parameter_value!r}{self._COLORS['RESET']}"

        return message
