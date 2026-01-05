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

import sqlite3
import datetime
import os
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
import json

from ms_service_profiler.utils.log import logger
from ms_service_profiler.parse_helper.constant import (MAJOR_TABLE_NAME, MINOR_TABLE_NAME, MAJOR_TABLE_COLS,
                                                       MINOR_TABLE_COLS, US_PER_SECOND, SLICE_TABLE_NAME, SLICE_TABLE_COLS)


def convert_db_to_df(file_path):
    major_sql_query = f"SELECT {','.join(MAJOR_TABLE_COLS)} FROM {MAJOR_TABLE_NAME} order by markId"
    minor_sql_query = f"SELECT {','.join(MINOR_TABLE_COLS)} FROM {MINOR_TABLE_NAME}"
    slice_sql_query = f"SELECT {','.join(SLICE_TABLE_COLS)} FROM {SLICE_TABLE_NAME} order by id"

    meta = dict()
    df = pd.DataFrame()

    with sqlite3.connect(file_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({MINOR_TABLE_NAME})")
        meta_columns = [row[1] for row in cursor.fetchall()]
        use_slice_logic = 'slice' in meta_columns

        try:
            cursor.execute(minor_sql_query)
            data = cursor.fetchall()
            for name, value in data:
                meta[name] = value
        except Exception as e:
            logger.warning("cannot read meta data from %r, due to %s", file_path, e)
            return df, meta, use_slice_logic

        if use_slice_logic:
            logger.info("Using slice logic for %r", file_path)
            try:
                df = pd.read_sql_query(slice_sql_query, conn)
            except Exception as e:
                logger.warning("cannot read slice data from %r, due to %s", file_path, e)
                return df, meta, use_slice_logic
            df = _convert_slice_to_mstx_format(df, meta)
        else:
            logger.info("Using mstx logic for %r", file_path)
            try:
                df = pd.read_sql_query(major_sql_query, conn)
            except Exception as e:
                logger.warning("cannot read prof data from %r, due to %s", file_path, e)
                return df, meta, use_slice_logic

            for name, value in data:
                df[name] = value

        file_name = os.path.basename(file_path)
        prof_id = os.path.splitext(file_name)[0]
        df["prof_id"] = prof_id
    return df, meta, use_slice_logic


def _convert_slice_to_mstx_format(slice_df, meta):
    """将 slice 表数据转换为 mstx 格式"""

    slice_df['markId'] = slice_df['id']
    slice_df['message'] = slice_df['args']

    for name, value in meta.items():
        slice_df[name] = value

    slice_df.rename(columns={'cat': 'domain'}, inplace=True)

    logger.debug("Successfully converted slice table to mstx format, %d records", len(slice_df))
    return slice_df


def convert_timestamp(timestamp: str):
    time = timestamp
    try:
        date_time = datetime.datetime.fromtimestamp(timestamp / US_PER_SECOND)
        time = date_time.strftime("%Y-%m-%d %H:%M:%S:%f")
    except Exception as e:
        logger.warning("%s: %s", e, timestamp)

    return time
