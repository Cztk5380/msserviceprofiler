# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import sqlite3
import datetime
import os
from concurrent.futures import ProcessPoolExecutor
import pandas as pd

from ms_service_profiler.utils.log import logger
from ms_service_profiler.parse_helper.constant import (MAJOR_TABLE_NAME, MINOR_TABLE_NAME, MAJOR_TABLE_COLS,
                                                       MINOR_TABLE_COLS, US_PER_SECOND)


def convert_db_to_df(file_path):
    major_sql_query = f"SELECT {','.join(MAJOR_TABLE_COLS)} FROM {MAJOR_TABLE_NAME} order by markId"
    minor_sql_query = f"SELECT {','.join(MINOR_TABLE_COLS)} FROM {MINOR_TABLE_NAME}"
    meta = dict()
    df = pd.DataFrame()
    with sqlite3.connect(file_path) as conn:
        try:
            df = pd.read_sql_query(major_sql_query, conn)
        except Exception as e:
            logger.warning("%s: %r", e, file_path)
            return df, meta

        cursor = conn.cursor()
        try:
            data = cursor.execute(minor_sql_query)
        except Exception as e:
            logger.warning("%s: %r", e, file_path)
            return df, meta

    try:
        for name, value in data:
            df[name] = value  # 后续删除
            meta[name] = value

        # file_path一定为 .db文件，无风险
        file_name = os.path.basename(file_path)
        prof_id = os.path.splitext(file_name)[0]
        df["prof_id"] = prof_id
    except Exception as e:
        logger.warning("%s: %r", e, file_path)
        return df, meta
    
    return df, meta


def convert_timestamp(timestamp: str):
    time = timestamp
    try:
        date_time = datetime.datetime.fromtimestamp(timestamp / US_PER_SECOND)
        time = date_time.strftime("%Y-%m-%d %H:%M:%S:%f")
    except Exception as e:
        logger.warning("%s: %s", e, timestamp)

    return time
