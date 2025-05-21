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

import re
import os
import stat

from .base import BasePathConstraint
from ..utils import get_file_size_config


class Exists(BasePathConstraint):
    description = "an existing path"

    def is_satisfied_by(self, path):
        return self._get_path_stat(path) is not None


class IsFile(BasePathConstraint):
    description = "a regular file"

    def is_satisfied_by(self, path):
        stat_result = self._get_path_stat(path)
        return stat_result is not None and stat.S_ISREG(stat_result.st_mode)


class IsDir(BasePathConstraint):
    description = "a directory"

    def is_satisfied_by(self, path):
        stat_result = self._get_path_stat(path)
        return stat_result is not None and stat.S_ISDIR(stat_result.st_mode)


class HasSoftLink(BasePathConstraint):
    """Check if path contains a soft link; if path does not exist, raise FileNotFoundError."""
    description = "a soft link"

    def is_satisfied_by(self, path):
        norm_path = os.path.normpath(os.path.abspath(path))
        components = norm_path.split(os.sep)

        current = os.path.sep
        for part in components[1:]:
            if not part:
                continue
            current = os.path.join(current, part)
            current_stat = self._get_path_stat(current)
            if current_stat is None:
                raise FileNotFoundError(f"Path component {current!r} does not exist.")
            if stat.S_ISLNK(current_stat.st_mode):
                return True

        final_stat = self._get_path_stat(norm_path)
        if final_stat is None:
            raise FileNotFoundError(f"Path {norm_path!r} does not exist.")

        return stat.S_ISLNK(final_stat.st_mode)


class IsReadable(BasePathConstraint):
    description = "a readable path"

    def is_satisfied_by(self, path):
        return os.access(path, os.R_OK)


class IsWritable(BasePathConstraint):
    description = "a writable path"

    def is_satisfied_by(self, path):
        return os.access(path, os.W_OK)


class IsExecutable(BasePathConstraint):
    description = "an executable path"

    def is_satisfied_by(self, path):
        return os.access(path, os.X_OK)


class IsWritableToGroupOrOthers(BasePathConstraint):
    description = "writable to group or others"

    def is_satisfied_by(self, path):
        stat_result = self._get_path_stat(path)
        if stat_result is None:
            raise FileNotFoundError(f"The path {path!r} does not exist or cannot be accessed.")

        return bool(stat_result.st_mode & (stat.S_IWGRP | stat.S_IWOTH))


class IsConsistentToCurrentUser(BasePathConstraint):
    description = "consistent with the current user"

    def is_satisfied_by(self, path):
        stat_result = self._get_path_stat(path)
        if stat_result is None:
            raise FileNotFoundError(f"The path {path!r} does not exist or cannot be accessed.")

        return stat_result.st_uid == os.geteuid()


class IsSizeReasonable(BasePathConstraint):
    description = "reasonable on its size"
    
    def __init__(self, *, size_limit=None, require_confirm=True, description=None):
        super().__init__(description=description)
        self.size_limit = size_limit
        self.require_confirm = require_confirm

    def is_satisfied_by(self, path):
        stat_result = self._get_path_stat(path)
        if stat_result is None:
            raise FileNotFoundError(f"The path {path!r} does not exist or cannot be accessed.")

        if not stat.S_ISREG(stat_result.st_mode):
            raise OSError(f"The path {path!r} is not a regular file.")

        return self._check_size(path, stat_result.st_size)

    def _check_size(self, path, file_size):
        if self.size_limit is None:
            from ..utils.constants import EXT_SIZE_MAPPING
            
            ext = os.path.splitext(path)[1]
            self.size_limit = EXT_SIZE_MAPPING.get(ext, max(EXT_SIZE_MAPPING.values()))

        is_reasonable = file_size < self.size_limit

        if not is_reasonable and self.require_confirm:
            return self._prompt_user_confirmation(path, file_size)

        return is_reasonable

    def _prompt_user_confirmation(self, path, file_size):
        prompt = (
            f"The file {path!r} is larger than expected ({file_size} Bytes). This could be a potential security threat."
            " Attempting to read such a file could potentially impact system performance.\n"
            "Please confirm your awareness of the risks associated with this action (y/n): "
        )
        confirm_pattern = re.compile(r'y(?:es)?', re.IGNORECASE)

        try:
            user_action = input(prompt)
        except Exception:
            return False

        return bool(confirm_pattern.match(user_action))
