# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import shutil
import sqlite3
import argparse
from pathlib import Path
import multiprocessing
import numpy as np

import pandas as pd

from ms_service_profiler.utils.file_open_check import FileStat
from ms_service_profiler.utils.check.rule import Rule
from ms_service_profiler.utils.error import DatabaseError
from ms_service_profiler.utils.file_open_check import ms_open
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.sec import traverse_dir_common_check, read_file_common_check

visual_db_fp = ''
db_write_lock = multiprocessing.Lock()
MAX_ITERATIONS = 10000
DATA_TABLE_NAME = 'data_table'
CREATE_DATA_TABLE_SQL = """
    CREATE TABLE data_table (id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,view_name TEXT);
"""
UPDATA_DATA_TABLE_SQL = """
    INSERT INTO data_table (name, view_name) VALUES (?,?);
"""
CURVE_VIEW_NAME_LIST = {
    # 折线图原始表名: 视图名称
    'batch': 'Batch_Size_by_Batch_ID_curve',
    'kvcache': 'Kvcache_Usage_Percent_curve',
    'prefill_gen_speed': 'Prefill_Generate_Speed_Latency_curve',
    'req_latency': 'Request_Latency_curve',
    'decode_gen_speed': 'Decode_Generate_Speed_Latency_curve',
    'first_token_latency': 'First_Token_Latency_curve',
    'request_status': 'Request_Status_curve'
}
TABLE_DATA_VIEW_NAME_LIST = {
    # 需要以纯表显示的db中的表名: data_table中的视图名称
    'batch': 'batch_info',
    'kvcache': 'kvcache_usage',
    'pd_split_communication': 'pd_split_communication',
    'request': 'request_data',
    'pd_split_kvcache': 'pd_split_pull_kvcache'
}
RENAME_COLUMNS_LIST = {
    # csv文件/db表名称: 需要重命名的列
    'batch': {
        'start_time': 'start_time(ms)', 'end_time': 'end_time(ms)', 'during_time': 'during_time(ms)'
    },
    'pd_split_kvcache': {
        'start_time': 'start_time(ms)', 'end_time': 'end_time(ms)', 'during_time': 'during_time(ms)',
        'start_datetime': 'start_datetime(ms)', 'end_datetime': 'end_datetime(ms)'
    },
    'kvcache': {
        'deviceBlock=': 'device_kvcache_left', 'start_time': 'timestamp(ms)',
        'start_datetime': 'start_datetime(ms)'
    },
    'pd_split_communication': {
        'http_req_time': 'http_req_time(ms)', 'send_request_time': 'send_request_time(ms)',
        'send_request_succ_time': 'send_request_succ_time(ms)', 'prefill_res_time': 'prefill_res_time(ms)',
        'requset_end_time': 'requset_end_time(ms)'
    },
    'request_data': {
        'start_time': 'start_time(ms)', 'execution_time': 'execution_time(ms)',
        'queue_wait_time': 'queue_wait_time(ms)', 'first_token_latency': 'first_token_latency(ms)'
    }
}


def write_result_to_db(df_param_list, name, create_sql_views=[]):
    try:
        # 写入数据库表
        for df, df_name in df_param_list:
            add_table_into_visual_db(df, df_name)

        # 创建视图
        create_sqlite_views(name, create_sql_views)
    except Exception as error:
        logger.warning(f"{name} write to db failed due to {error}")


def write_result_to_csv(df, output, name):
    if name in RENAME_COLUMNS_LIST.keys():
        df.rename(columns=RENAME_COLUMNS_LIST[name])
    save_dataframe_to_csv(df, output, f"{name}.csv")


def create_view_with_renamed_column(cursor, table_name, view_name):
    # 获取所有列名
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]  # 第2个元素是列名
    
    # 构建SELECT部分，重命名指定列
    select_parts = []
    for col in columns:
        if col in RENAME_COLUMNS_LIST.get(RENAME_COLUMNS_LIST, {}).keys():
            select_parts.append(f"{col} AS {RENAME_COLUMNS_LIST[table_name][col]}")
        else:
            select_parts.append(col)
    
    select_clause = ", ".join(select_parts)

    # 创建视图
    create_view_sql = f"""
    CREATE VIEW {view_name} AS
    SELECT {select_clause}
    FROM {table_name}
    """

    cursor.execute(create_view_sql)


def del_all_visual_table(views, cursor):
    for view in views:
        if view[0] in CURVE_VIEW_NAME_LIST.values() or\
            view[0] in TABLE_DATA_VIEW_NAME_LIST.values():
         cursor.execute(f"DROP VIEW IF EXISTS {view[0]};")


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

        # 创建data_table
        cursor.execute(f"DROP TABLE IF EXISTS {DATA_TABLE_NAME}")
        cursor.execute(CREATE_DATA_TABLE_SQL)

        # 获取所有视图名称
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view';")
        views = cursor.fetchall()

        # 删除所有视图
        del_all_visual_table(views, cursor)
    except Exception as ex:
        conn.rollback()  # 失败时回滚
        raise DatabaseError("Cannot create sqlite database.") from ex
    finally:
        if conn:
            conn.close()


def create_sqlite_views(name, create_view_sql=[]):
    with db_write_lock:
        with ms_open(visual_db_fp, "a") as f:
            try:
                conn = sqlite3.connect(visual_db_fp)
                cursor = conn.cursor()
                for sql in create_view_sql:
                    cursor.execute(sql)
                if name in TABLE_DATA_VIEW_NAME_LIST.keys():
                    create_view_with_renamed_column(cursor, name, TABLE_DATA_VIEW_NAME_LIST[name])
                conn.commit()
                conn.close()
            except Exception as ex:
                conn.rollback()  # 失败时回滚
                raise DatabaseError(f"Cannot update sqlite database when create {name} views.") from ex


def handle_sqlite_table_list(table_list, cursor):
    for name, create_stmt in table_list.items():
        cursor.execute(f"DROP TABLE IF EXISTS {name}")
        cursor.execute(create_stmt)


def create_sqlite_tables(table_list):
    with db_write_lock:
        with ms_open(visual_db_fp, "a") as f:
            try:
                conn = sqlite3.connect(visual_db_fp)
                cursor = conn.cursor()
                handle_sqlite_table_list(table_list, cursor)
                conn.commit()
                conn.close()
            except Exception as ex:
                raise DatabaseError("Cannot update sqlite database when create trace table.") from ex


def get_db_connection():
    with db_write_lock:
        with ms_open(visual_db_fp, "a") as f:
            return sqlite3.connect(visual_db_fp)


def add_record_to_data_table(table_name, conn):
    if table_name in TABLE_DATA_VIEW_NAME_LIST.keys():
        cursor = conn.cursor()
        view_name = TABLE_DATA_VIEW_NAME_LIST[table_name]
        cursor.execute(UPDATA_DATA_TABLE_SQL, (view_name, view_name))


def add_table_into_visual_db(df, table_name):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        logger.warning("Writing table %r failed due to invalid dataframe:\n\t%s", table_name, df)
        return

    for col in df:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)

    with db_write_lock:
        with ms_open(visual_db_fp, "a") as f:
            try:
                conn = sqlite3.connect(visual_db_fp)
                df.to_sql(table_name, conn, if_exists='replace', index=False)

                # 判断如果此表需要在Insight中用纯表展示，则刷新data_table中记录
                add_record_to_data_table(table_name, conn)
                conn.commit()
                conn.close()
            except Exception as ex:
                conn.rollback()  # 失败时回滚
                raise DatabaseError("Cannot update sqlite database.") from ex


def save_dataframe_to_csv(filtered_df, output, file_name):
    if filtered_df is None or not isinstance(filtered_df, pd.DataFrame) or filtered_df.empty:
        logger.warning("Writing csv %r failed due to invalid dataframe:\n\t%s", file_name, filtered_df)
        return

    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = output_path / file_name
        file_path = str(file_path)
        with ms_open(file_path, "w") as f:
            filtered_df.to_csv(f, index=False)
            logger.info(f"Write to {file_name} success.")


def _check_directory(dir_path, iteration_count):
    """检查单个文件夹的安全性"""
    try:
        # 检查循环数
        iteration_count += 1
        if iteration_count > MAX_ITERATIONS:
            raise argparse.ArgumentTypeError(f"Maximum iteration count ({MAX_ITERATIONS}) exceeded.")

        # 校验文件夹
        traverse_dir_common_check(dir_path)
    except argparse.ArgumentTypeError as e:
        raise argparse.ArgumentTypeError(f"Directory is NOT safe")


def _check_file(file_path, iteration_count):
    """检查单个文件的安全性"""
    try:
        # 检查循环数
        iteration_count += 1
        if iteration_count > MAX_ITERATIONS:
            raise argparse.ArgumentTypeError(f"Maximum iteration count ({MAX_ITERATIONS}) exceeded.")

        # 校验文件
        read_file_common_check(file_path)
    except argparse.ArgumentTypeError as e:
        raise argparse.ArgumentTypeError(f"File is NOT safe")


def check_input_path_valid(path):
    try:
        # 首先校验传入路径是否为目录，并确保目录可遍历
        safe_path = traverse_dir_common_check(path)

        # 初始化计数器
        iteration_count = 0

        # 递归检查目录下的所有文件和文件夹
        for root, dirs, files in os.walk(safe_path):
            # 检查文件夹
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                _check_directory(dir_path, iteration_count)

            # 检查文件
            for file_name in files:
                file_path = os.path.join(root, file_name)
                _check_file(file_path, iteration_count)

        return safe_path

    except argparse.ArgumentTypeError as e:
        raise argparse.ArgumentTypeError(f"Input path is illegal. {str(e)}")


def check_output_path_valid(path):
    path = os.path.abspath(path)
    if not os.path.isdir(path):  # not exists or exists but not directory
        os.makedirs(path, mode=0o750)  # create
    else:
        check_path = Rule.output_dir().check(path)
        if not check_path:
            raise argparse.ArgumentTypeError("Output path %r is incorrect due to %s, please check", path, check_path)
    return path


def find_file_in_dir(directory, filename):
    count = 0
    max_iter = MAX_ITERATIONS
 
    for _, _, files in os.walk(directory):
        count += len(files)
        if count > max_iter:
            break
        if filename in files:
            return True
    return False


def find_all_file_complete(directory, filename='all_file.complete'):
    count = 0
    data_count = 0
    data_with_file_count = 0
 
    for root, _, files in os.walk(directory):
        count += len(files)
        if count > MAX_ITERATIONS:
            break
        if os.path.basename(root) == 'data':
            data_count += 1
            if filename in files:
                data_with_file_count += 1

    # 所有data文件夹下都应有一个all_file.complete
    return data_count == data_with_file_count


def delete_dir_safely(path):
    # 删除文件安全校验
    try:
        check_input_path_valid(path)
    except Exception as e:
        logger.error(f'check_input_path_valid {path} failed, due to {e}')
        return

    try:
        shutil.rmtree(path)
        logger.warning(f"Delete {path}")
    except Exception as e:
        logger.error(f"Delete failed: {path}, error: {e}")


def truncate_timestamp_np(s: pd.Series) -> pd.Series:
    arr = s.to_numpy(dtype='str')
    return pd.Series(np.core.defchararray.ljust(arr, len(arr[0])-3))


def check_domain_valid(df, domain_list, exporter_name):
    # 校验采集到的domain是否满足解析需要
    current_domains = set(df['domain'])

    # 检查domain_list中的每个domain是否都存在
    missing_domains = [domain for domain in domain_list if domain not in current_domains]

    if missing_domains:
        logger.warning(f"Exporter {exporter_name} - missing domains: {missing_domains}")

    return True
