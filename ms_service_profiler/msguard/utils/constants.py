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


CONFIG_FILE_MAX_SIZE = 1 * 1024 * 1024 # work for .ini config file
TEXT_FILE_MAX_SIZE = 5 * 1024 * 1024 * 1024 # work for txt, csv, py
JSON_FILE_MAX_SIZE = 1024 * 1024 * 1024
DB_MAX_SIZE = 50 * 1024 * 1024 * 1024
LOG_FILE_MAX_SIZE = 5 * 1024 * 1024


EXT_SIZE_MAPPING = {
    '.db': DB_MAX_SIZE,
    ".ini": CONFIG_FILE_MAX_SIZE,
    '.csv': TEXT_FILE_MAX_SIZE,
    '.txt': TEXT_FILE_MAX_SIZE,
    '.json': JSON_FILE_MAX_SIZE,
    '.log': LOG_FILE_MAX_SIZE
}

DEFAULT_MAX_FILES = 10000
DEFAULT_MAX_DEPTHS = 100
DEFAULT_FILE_MODE = 0o640
DEFAULT_DIR_MODE = 0o750
VALID_OPEN_MODES = {'r', 'w', 'x', 'a', 'b', 't', '+'}
