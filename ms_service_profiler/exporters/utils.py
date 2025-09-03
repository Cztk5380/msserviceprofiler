# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import re
import shutil
import sqlite3
import argparse
from pathlib import Path
import multiprocessing
import numpy as np

import pandas as pd

from ms_service_profiler.utils.check.rule import Rule
from ms_service_profiler.utils.error import DatabaseError
from ms_service_profiler.utils.file_open_check import ms_open
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.sec import traverse_dir_common_check, read_file_common_check

visual_db_fp = ''
db_write_lock = multiprocessing.Lock()
CSV_BLACK_LIST = r'^[＋－＝％＠\+\-=%@]|;[＋－＝％＠\+\-=%@]'
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
    'request_status': 'Request_Status_curve',
    'coordinator': 'Coordinator_curve',
}
TABLE_DATA_VIEW_NAME_LIST = {
    # 需要以纯表显示的db中的表名: data_table中的视图名称
    # data_table中(name, view_name)都为视图名称
    'batch': 'batch_info',
    'kvcache': 'kvcache_usage',
    'pd_split_communication': 'pd_communication_info',
    'request': 'request_data',
    'pd_split_kvcache': 'pd_split_pull_kvcache',
    'forward': 'forward_info',
    'coordinator': 'coordinator_info',
}


class COLUMN_CONST:
    HOSTUID_COLUMN = 'hostuid'
    PID_COLUMN = 'pid'
    START_TIME_COLUMN = 'start_time'
    TIMESTAMP_MS_COLUMN = 'timestamp(ms)'
    RELATIVE_TIMESTAMP_MS_COLUMN = 'relative_timestamp(ms)'
    DOMAIN_COLUMN = 'domain'
    NAME_COLUMN = 'name'
    STATUS_COLUMN = 'status'
    QUEUESIZE_COLUMN = 'QueueSize='


def write_result_to_db(df_param_list, create_view_sql=None, table_name="", rename_cols=None):
    """
        df_param_list: [[需要存入db中table的df, table name], [...]]
        create_view_sql: 需要创建用于折线图展示的视图的sql语句列表
        table_name: 需要以纯表显示的db中的表名(df_param_list中最多只有一个表需要以纯表形式展示)
        rename_cols: 纯表展示数据需要修改的列名，该视图创建语句动态生成
    """
    try:
        create_view_sql = create_view_sql or []
        rename_cols = rename_cols or []
        table_add_success = True
        for df, df_name in df_param_list:
            table_add_success = add_table_into_visual_db(df, df_name) and table_add_success

        if table_add_success:
            create_sqlite_views(table_name, create_view_sql, rename_cols)

    except Exception as error:
        logger.warning(f"{table_name} write to db table failed due to {error}")


def write_result_to_csv(df, output, csv_name, rename_col):
    df = df.rename(columns=rename_col)
    save_dataframe_to_csv(df, output, f"{csv_name}.csv")


def create_view_with_renamed_column(cursor, table_name, view_name, rename_cols):
    # 获取所有列名
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]  # 第2个元素是列名

    # 构建SELECT部分，重命名指定列
    select_parts = []
    for col in columns:
        if col in rename_cols:
            select_parts.append(f'"{col}" AS "{rename_cols[col]}"')
        else:
            select_parts.append(col)

    select_clause = ", ".join(select_parts)

    # 创建视图
    create_view_sql = f"""
    CREATE VIEW IF NOT EXISTS {view_name} AS
    SELECT {select_clause}
    FROM {table_name}
    """
    cursor.execute(create_view_sql)


def del_all_visual_table(views, cursor):
    for view in views:
        if not view or len(view) < 1:
            continue
        if view[0] in CURVE_VIEW_NAME_LIST.values() or view[0] in TABLE_DATA_VIEW_NAME_LIST.values():
            cursor.execute(f"DROP VIEW IF EXISTS {view[0]};")


def create_sqlite_db(output):
    global visual_db_fp

    if visual_db_fp != '':
        return

    if not os.path.exists(output):
        os.makedirs(output, mode=0o750, exist_ok=True)
    visual_db_fp = os.path.join(output, 'profiler.db')
    with ms_open(visual_db_fp, 'a'):
        pass
    os.chmod(visual_db_fp, 0o640)
    conn = None
    cursor = None
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
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_views_with_sqls(cursor, create_view_sql):
    for sql in create_view_sql:
        cursor.execute(sql)


def create_views_with_table_name(cursor, table_name, rename_cols):
    if table_name in TABLE_DATA_VIEW_NAME_LIST.keys():
        create_view_with_renamed_column(cursor, table_name,
            TABLE_DATA_VIEW_NAME_LIST[table_name], rename_cols)


def create_sqlite_views(table_name, create_view_sql, rename_cols):
    with db_write_lock:
        with ms_open(visual_db_fp, "a"):
            try:
                conn = sqlite3.connect(visual_db_fp)
                cursor = conn.cursor()
                create_views_with_sqls(cursor, create_view_sql)
                create_views_with_table_name(cursor, table_name, rename_cols)
                conn.commit()
                conn.close()
            except Exception as ex:
                conn.rollback()  # 失败时回滚
                raise DatabaseError(f"Cannot update sqlite {table_name} views. due to {ex}") from ex


def handle_sqlite_table_list(table_list, cursor):
    for name, create_stmt in table_list.items():
        cursor.execute(f"DROP TABLE IF EXISTS {name}")
        cursor.execute(create_stmt)


def create_sqlite_tables(table_list):
    with db_write_lock:
        with ms_open(visual_db_fp, "a"):
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
        with ms_open(visual_db_fp, "a"):
            return sqlite3.connect(visual_db_fp)


def add_record_to_data_table(table_name, conn):
    if table_name in TABLE_DATA_VIEW_NAME_LIST.keys():
        cursor = conn.cursor()
        view_name = TABLE_DATA_VIEW_NAME_LIST[table_name]
        cursor.execute(UPDATA_DATA_TABLE_SQL, (view_name, view_name))


def add_table_into_visual_db(df, table_name, allow_empty=False):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or len(df.columns) == 0:
        logger.debug("nothing to write to table %r. due to dataframe is:%s", table_name, df)
        if not allow_empty:
            logger.warning("nothing to write to table %r.", table_name)
        return False

    for col in df:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)

    with db_write_lock:
        with ms_open(visual_db_fp, "a"):
            try:
                conn = sqlite3.connect(visual_db_fp)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=300000")  # 等5分钟
                df.to_sql(table_name, conn, if_exists='replace', index=False)

                # 判断如果此表需要在Insight中用纯表展示，则刷新data_table中记录
                add_record_to_data_table(table_name, conn)
                conn.commit()
                conn.close()
            except Exception as ex:
                conn.rollback()  # 失败时回滚
                raise DatabaseError(f"Cannot update {table_name} sqlite database.") from ex
    return True


def save_dataframe_to_csv(filtered_df, output, file_name, check_columns=None, allow_empty=False):
    if filtered_df is None or not isinstance(filtered_df, pd.DataFrame) or filtered_df.empty or output is None:
        logger.debug("nothing to write to %r due to empty data : %s", file_name, filtered_df)
        if not allow_empty:
            logger.warning("nothing to write to %r .", file_name)
        return

    # check column names
    for col in filtered_df.columns:
        if not _check_csv_value_is_valid(col):
            logger.error(f"Column name [{col}] contains malicious value.")
            return

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_path = output_path / file_name
    file_path = str(file_path)

    if not _preprocess_dataframe(filtered_df, check_columns):
        logger.warning(f"DataFrame contains invalid values. Aborting write to {file_name}.")
        return

    with ms_open(file_path, "w") as f:
        filtered_df.to_csv(f, index=False)
        logger.info(f"Write to {file_name} success.")


def _preprocess_dataframe(df, check_columns=None):
    if not check_columns:
        return True

    # 校验单元格是否合法
    for col in check_columns:
        if col in df.columns:
            has_invalid_value = any(not _check_csv_value_is_valid(x) for x in df[col])
            if has_invalid_value:
                logger.warning(f"Column {col} contains malicious values")
                return False

    return True


def _check_csv_value_is_valid(value: str):
    if not isinstance(value, str):
        return True
    try:
        # -1.00 or +1.00 should be considered as digit numbers
        float(value)
    except ValueError:
        return not bool(re.compile(CSV_BLACK_LIST).search(value))
    return True


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
        raise argparse.ArgumentTypeError("Directory is NOT safe") from e


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
        raise argparse.ArgumentTypeError("File is NOT safe") from e


def is_empty_directory(directory):
    with os.scandir(directory) as entries:
        return len(list(entries)) == 0


def check_input_dir_valid(path):
    try:
        # 首先校验传入路径是否为目录，并确保目录可遍历
        safe_path = traverse_dir_common_check(path)

        # 对空文件夹进行校验
        if is_empty_directory(safe_path):
            logger.error(f"Input path is empty.: {safe_path!r}")

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
        check_input_dir_valid(path)
    except Exception as e:
        logger.error(f'check input dir_valid {path} failed, due to {e}')
        return

    try:
        shutil.rmtree(path)
        logger.debug(f"Delete {path}")
    except Exception as e:
        logger.error(f"Delete {path} failed, due to : {e}")


def truncate_timestamp_np(s: pd.Series) -> pd.Series:
    arr = s.to_numpy(dtype='str')
    return pd.Series(np.core.defchararray.ljust(arr, len(arr[0])-3))


def check_domain_valid(df, domain_list, exporter_name):
    # 校验采集到的domain是否满足解析需要
    current_domains = set(df['domain'])

    # 检查domain_list中的每个domain是否都存在
    missing_domains = [domain for domain in domain_list if domain not in current_domains]

    if missing_domains:
        logger.warning(f"Exporter {exporter_name} will skip, the prof data of domain {missing_domains} is missing")

    return True


def check_columns_valid(df, column_list, exporter_name):
    current_columns = set(df.columns)

    missing_columns = [column for column in column_list if column not in current_columns]

    if missing_columns:
        logger.warning(f"Exporter {exporter_name} will skip. the attribute {missing_columns} in prof data is missing")
        return False
    return True
