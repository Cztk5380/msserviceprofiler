# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import sqlite3

visual_db_fp = ''


def create_sqlite_db(output):
    global visual_db_fp

    if visual_db_fp != '':
        return

    if not os.path.exists(output):
        os.makedirs(output)
    visual_db_fp = os.path.join(output, '.profiler.db')
    conn = sqlite3.connect(visual_db_fp)
    conn.isolation_level = None
    cursor = conn.cursor()
    conn.close()


def add_table_into_visual_db(df, table_name):
    conn = sqlite3.connect(visual_db_fp)
    df.to_sql(table_name, conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()
