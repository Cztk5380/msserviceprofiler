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
from ms_service_profiler.utils.file_open_check import FileStat


def check_input_path_valid(path):
    try:
        file_stat = FileStat(path)
    except Exception as err:
        raise argparse.ArgumentTypeError(f"input path:{path} is illegal. Please check.")
    if not file_stat.is_dir:
        raise argparse.ArgumentTypeError(f"Path is not a valid directory: {path}")
    return path
