# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import sqlite3
import argparse
from pathlib import Path
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


def save_dataframe_to_csv(filtered_df, output, file_name):
    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = output_path / file_name
        filtered_df.to_csv(file_path, index=False)


def check_input_path_valid(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path does not exist: {path}")
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"Path is not a valid directory: {path}")
    if '..' in path:
        raise argparse.ArgumentTypeError(f"Path contains illegal characters: {path}")
    return path


def check_output_path_valid(path):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        os.makedirs(path, mode=0o755)
    else:
        os.chmod(path, 0o755)
    if not os.access(path, os.W_OK):
        raise argparse.ArgumentTypeError(f"Output path is not writable: {path}")
    return path