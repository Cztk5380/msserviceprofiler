import sqlite3
import datetime
import pandas as pd
from concurrent.futures import ProcessPoolExecutor

from ms_service_profiler.utils.log import logger
from ms_service_profiler.parse_helper.constant import MAJOR_TABLE_NAME, MINOR_TABLE_NAME, MAJOR_TABLE_COLS, MINOR_TABLE_COLS, US_PER_SECOND


def _convert_db_to_df(file_path):
    major_sql_query = f"SELECT {','.join(MAJOR_TABLE_COLS)} FROM {MAJOR_TABLE_NAME} order by markId"
    minor_sql_query = f"SELECT {','.join(MINOR_TABLE_COLS)} FROM {MINOR_TABLE_NAME}"

    df = pd.DataFrame()
    with sqlite3.connect(file_path) as conn:
        try:
           df = pd.read_sql_query(major_sql_query, conn)
        except Exception as e:
            logger.warning("%s: %r", e, file_path)
            return df

        cursor = conn.cursor()
        try:
            data = cursor.execute(minor_sql_query)
        except Exception as e:
            logger.warning("%s: %r", e, file_path)
            return df

    try:
        for name, value in data:
            df[name] = value
    except Exception as e:
        logger.warning("%s: %r", e, file_path)
        return df

    return df


def convert_db_to_df(files, max_workers=8):
    dfs = []
    with ProcessPoolExecutor(max_workers) as executor:
        dfs = list(executor.map(_convert_db_to_df, files))

    return pd.concat(dfs, ignore_index=True)


def convert_timestamp(timestamp: str):
    time = timestamp
    try:
        date_time = datetime.datetime.fromtimestamp(timestamp / US_PER_SECOND)
        time = date_time.strftime("%Y-%m-%d %H:%M:%S:%f")
    except Exception as e:
        logger.warning("%s: %s", e, timestamp)

    return time
