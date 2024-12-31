# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import sqlite3
import multiprocessing

from ms_service_profiler.utils.error import DatabaseError

visual_db_fp = ''
db_write_lock = multiprocessing.Lock()


def create_sqlite_db(output):
    global visual_db_fp

    if visual_db_fp != '':
        return

    if not os.path.exists(output):
        os.makedirs(output)
    visual_db_fp = os.path.join(output, 'profiler.db')
    try:
        conn = sqlite3.connect(visual_db_fp)
        conn.isolation_level = None
        cursor = conn.cursor()
        conn.close()
    except Exception as ex:
        raise DatabaseError("Cannot create sqlite database.") from ex


def add_table_into_visual_db(df, table_name):
    with db_write_lock:
        try:
            conn = sqlite3.connect(visual_db_fp)
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            conn.commit()
            conn.close()
        except Exception as ex:
            raise DatabaseError("Cannot update sqlite database.") from ex
