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
import re
from typing import List, Tuple, Set

from ..common.utils import logger
from ..common.sec import read_file_common_check


class FileCollector(object):
    def __init__(self, pattern: re.Pattern, max_iter=100) -> None:
        self.pattern = pattern
        self.max_iter = max_iter

        self._validate_param()

    def collect_pairs(self, dir_path_a: str, dir_path_b: str) -> List[Tuple]:
        file_set_a = self._collect(dir_path_a)
        file_set_b = self._collect(dir_path_b)

        intersection = file_set_a & file_set_b
        diff = file_set_a ^ file_set_b
        if diff:
            logger.error(
                "The files shown below are not matched in both directories %r and will not be compared",
                list(diff)
            )

        return [
            (os.path.join(dir_path_a, file_path), os.path.join(dir_path_b, file_path))
            for file_path in intersection
        ]

    def _validate_param(self):
        if not isinstance(self.pattern, re.Pattern):
            raise TypeError("'pattern' type should be 're.Pattern', but got %r instead" % type(self.pattern).__name__)

        if not isinstance(self.max_iter, int):
            raise TypeError("'max_iter' type should be 'int', but got %r instead" % type(self.max_iter).__name__)
        
        if self.max_iter < 1:
            raise ValueError("'max_iter' should not be less than 1")

    def _collect(self, dir_path: str) -> Set:
        res = set()

        files = os.listdir(dir_path)

        if len(files) > self.max_iter:
            raise RuntimeError("The number of the files under %r exceeds the iteration limits, "
                               "please use another directory instead" % dir_path)

        for file_path in files:
            if self.pattern.match(file_path):
                full_path = os.path.join(dir_path, file_path)
                
                try:
                    read_file_common_check(full_path, raise_argparse=False)
                except OSError as e:
                    logger.warning("%r will not be processed due to %s", full_path, e)
                    continue

                res.add(file_path)

        return res
