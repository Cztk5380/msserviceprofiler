# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.


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
