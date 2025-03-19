# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import sqlite3
import argparse
from pathlib import Path
import multiprocessing
from ms_service_profiler.utils.file_open_check import FileStat
from ms_service_profiler.utils.check.rule import Rule
from ms_service_profiler.utils.error import DatabaseError
from ms_service_profiler.utils.file_open_check import ms_open
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
        with ms_open(visual_db_fp, "w") as f:
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
        file_path = str(file_path)
        with ms_open(file_path, "w") as f:
            filtered_df.to_csv(f, index=False)


def check_input_path_valid(path):
    try:
        file_stat = FileStat(path)
    except Exception as err:
        raise argparse.ArgumentTypeError(f"input path:{path} is illegal. Please check.")
    if not file_stat.is_dir:
        raise argparse.ArgumentTypeError(f"Path is not a valid directory: {path}")
    return path


def check_output_path_valid(path):
    path = os.path.abspath(path)
    if not os.path.isdir(path):  # not exists or exists but not directory
        os.makedirs(path, mode=0o750)  # create
    else:
        check_path = Rule.input_dir().check(path)
        if not check_path:
            raise argparse.ArgumentTypeError("Output path %r is incorrect due to %s, please check", path, check_path)
    if not os.access(path, os.W_OK):
        raise argparse.ArgumentTypeError(f"Output path is not writable: {path}")
    return path