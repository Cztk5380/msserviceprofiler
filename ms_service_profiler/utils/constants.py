# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import re


PATH_WHITE_LIST_REGEX = re.compile(r"[^_A-Za-z0-9/.-]")


CONFIG_FILE_MAX_SIZE = 1 * 1024 * 1024  # work for .ini config file
TEXT_FILE_MAX_SIZE = 100 * 1024 * 1024  # work for json, txt, csv


EXT_SIZE_MAPPING = {
    '.csv': TEXT_FILE_MAX_SIZE,
    '.json': TEXT_FILE_MAX_SIZE,
    '.txt': TEXT_FILE_MAX_SIZE,
    '.py': TEXT_FILE_MAX_SIZE
}
