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
from collections import deque

from .exception import WalkLimitError
from ..validation import validate_params
from ..constraints import Rule, where
from ..utils.constants import (
    DEFAULT_FILE_MODE, DEFAULT_MAX_FILES, DEFAULT_MAX_DEPTHS, VALID_OPEN_MODES,
    DEFAULT_DIR_MODE
)


@validate_params({"root_dir": Rule.input_dir_traverse})
def walk_s(
    root_dir,
    *,
    dir_rule=Rule.input_dir_traverse,
    file_rule=Rule.input_file_read,
    max_files=DEFAULT_MAX_FILES,
    max_depths=DEFAULT_MAX_DEPTHS
):
    def _process(dir_rule, file_rule, file_scanned, max_depths, max_files, queue):
        current_dir, current_depth = queue.pop()
        if current_depth > max_depths:
            raise WalkLimitError(f"Limit exceeded: {current_depth} / {max_depths}")
        for it in os.scandir(current_dir):
            file_scanned += 1
            if file_scanned > max_files:
                raise WalkLimitError(f"Limit exceeded: {file_scanned} / {max_files}")

            if it.is_dir(follow_symlinks=False):
                if dir_rule is None or dir_rule.is_satisfied_by(it.path):
                    yield it.path
                    queue.append((it.path, current_depth + 1))

            elif it.is_file(follow_symlinks=False):
                if file_rule is None or file_rule.is_satisfied_by(it.path):
                    yield it.path

    depth = 0
    root_dir = os.path.realpath(root_dir)
    queue = deque([(root_dir, depth)])
    file_scanned = 0

    while queue:
        yield from _process(dir_rule, file_rule, file_scanned, max_depths, max_files, queue)


def open_s(path, mode='r', **kwargs):
    if not set(mode).issubset(VALID_OPEN_MODES):
        raise ValueError(
            f"'mode' must be a combination of {VALID_OPEN_MODES}. Got {mode} instead"
        )

    flags = 0
    if '+' in mode:
        flags |= os.O_RDWR
    elif 'r' in mode:
        flags |= os.O_RDONLY
    else:
        flags |= os.O_WRONLY

    if 'w' in mode or 'x' in mode:
        flags |= os.O_CREAT
    if 'w' in mode:
        flags |= os.O_TRUNC
    if 'x' in mode:
        flags |= os.O_EXCL
    if 'a' in mode:
        flags |= os.O_APPEND | os.O_CREAT

    if 'b' in mode:
        flags |= getattr(os, 'O_BINARY', 0)

    @validate_params(
        {
            "path": where(
                'r' in mode,
                Rule.input_file_read,
                Rule.output_path_write,
                description="open file in read mode"
            )
        }
    )
    def get_fd(path, flags):
        return os.open(path, flags, mode=DEFAULT_FILE_MODE)

    fd = get_fd(path, flags)
    return os.fdopen(fd, mode, **kwargs)


def touch_s(path, mode=DEFAULT_FILE_MODE, exist_ok=True):
    if not path:
        raise ValueError("Cannot create a file with empty name")

    if exist_ok:
        try:
            os.utime(path, None)
        except OSError:
            pass
        else:
            return
    flags = os.O_CREAT | os.O_WRONLY
    if not exist_ok:
        flags |= os.O_EXCL
    fd = os.open(path, flags, mode)
    os.close(fd)


def mkdir_s(path, mode=DEFAULT_DIR_MODE, exist_ok=True):
    if not path:
        raise ValueError("Cannot create a directory with empty name")

    real_path = os.path.realpath(path)
    components = real_path.split(os.sep)

    current = os.path.sep
    for part in components[1:-1]:
        current = os.path.join(current, part)
        if os.path.isdir(current):
            continue

        try:
            os.mkdir(current, mode)
        except OSError:
            if not exist_ok or not os.path.isdir(current):
                raise

    try:
        os.mkdir(real_path, mode)
    except OSError:
        if not exist_ok or not os.path.isdir(real_path):
            raise
