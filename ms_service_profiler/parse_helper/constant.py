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

MAJOR_TABLE_NAME = "mstx"
MINOR_TABLE_NAME = "meta"
SLICE_TABLE_NAME = "slice"

SLICE_TABLE_COLS = ["id", "timestamp", "duration", "name", "depth", "track_id", "cat", "args", "cname", "end_time",
                    "flag_id", "pid", "tid"]
MAJOR_TABLE_COLS = ["markId", "message", "pid", "tid", "timestamp", "endTimestamp"]
MINOR_TABLE_COLS = ["name", "value"]

US_PER_SECOND = 1000 * 1000