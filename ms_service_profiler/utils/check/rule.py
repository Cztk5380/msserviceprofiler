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

from ms_service_profiler.utils.check.path_checker import PathChecker
from ms_service_profiler.utils.check.checker import Checker


class Rule:
    @staticmethod
    def none() -> Checker:
        return Checker().is_none()

    @staticmethod
    def path() -> PathChecker:
        return PathChecker()

    @staticmethod
    def config_file() -> PathChecker:
        return PathChecker().exists().is_file().as_default()

    @staticmethod
    def input_file() -> PathChecker:
        return PathChecker().exists().as_default()

    @staticmethod
    def input_dir() -> PathChecker:
        return PathChecker().exists().is_dir().as_default()

    @staticmethod
    def output_dir() -> PathChecker:
        return Rule.path().any(Rule.anti(PathChecker().exists()), PathChecker().is_dir()).as_default()

    @staticmethod
    def any(*rules: Checker) -> Checker:
        return Checker().any(*rules)

    @staticmethod
    def anti(rule: Checker) -> Checker:
        return Checker().anti(rule)
