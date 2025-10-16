from pytest_check import check
import os
import pytest
import random
import sqlite3
from contextlib import contextmanager, ExitStack

import pandas as pd
from ms_service_profiler.exporters.utils import CURVE_VIEW_NAME_LIST_COMPETITION
from test.st.checker.checker_utils import check_df_has_no_empty_line, check_df_expected_column


@contextmanager
def sqlite_cursor(conn):
    if conn is None:
        raise ValueError("Connection is None")
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


@contextmanager
def db_connect(db_path):
    with ExitStack() as stack:
        # 依次调用 enter，并确保 exit 顺序相反
        pytest_checker = stack.enter_context(check(f"check[{db_path}]"))
        conn = stack.enter_context(DbConnect(db_path))
        yield conn


class DbConnect:
    def __init__(self, db_path) -> None:
        assert os.path.exists(db_path)
        self.conn = sqlite3.connect(db_path)

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


def check_table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    table_exists = cursor.fetchone()
    assert table_exists is not None, f"table {table_name} not exists"


def check_view_exists(cursor, view_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name=?", (view_name,))
    table_exists = cursor.fetchone()
    assert table_exists is not None, f"view {view_name} not exists"


def read_table_to_df(conn, table_name):
    return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def check_and_get_df_from_table(conn, cursor, table_name, col_names, allow_empty):
    # 是否存在
    check_table_exists(cursor, table_name)
    df = read_table_to_df(conn, table_name)

    # 是否为空
    if not allow_empty:
        assert len(df) > 0, f"{table_name} is empty."

    # 没有空行
    check_df_has_no_empty_line(df)

    # 表头
    check_df_expected_column(df, col_names)
    return df


def check_latency_tables(conn, complete_req_cnt=0):
    with sqlite_cursor(conn) as cursor:
        expected_header = ["avg", "p50", "p90", "p99", "timestamp"]
        with check("check table decode_gen_speed"):
            check_and_get_df_from_table(conn, cursor, "decode_gen_speed", expected_header, complete_req_cnt == 0)
        with check("check table:first_token_latency"):
            check_and_get_df_from_table(conn, cursor, "first_token_latency", expected_header, complete_req_cnt == 0)
        with check("check table:prefill_gen_speed"):
            check_and_get_df_from_table(conn, cursor, "prefill_gen_speed", expected_header, complete_req_cnt == 0)
        with check("check table:req_latency"):
            check_and_get_df_from_table(conn, cursor, "req_latency", expected_header, complete_req_cnt == 0)


def check_kvcache_table(conn, complete_req_cnt=0):
    table_name = "kvcache"
    with sqlite_cursor(conn) as cursor:
        with check(table_name):
            # 表头
            expected_header = ["rid", "name", "start_datetime", "device_kvcache_left", "kvcache_usage_rate"]
            check_and_get_df_from_table(conn, cursor, table_name, expected_header, complete_req_cnt == 0)


def check_req_status_table(conn, complete_req_cnt=0):
    table_name = "request_status"
    with sqlite_cursor(conn) as cursor:
        with check(table_name):
            # 表头
            expected_header = ["timestamp", "WAITING", "PENDING", "RUNNING"]
            check_and_get_df_from_table(conn, cursor, table_name, expected_header, complete_req_cnt == 0)


def check_insight_tables(conn, complete_req_cnt=0):
    allow = complete_req_cnt == 0
    with sqlite_cursor(conn) as cursor:
        with check("counter"):
            check_and_get_df_from_table(conn, cursor, "counter", ["id", "name", "pid", "args", "timestamp"], allow)
        with check("flow"):
            check_and_get_df_from_table(
                conn, cursor, "flow", ["id", "flow_id", "name", "cat", "timestamp", "track_id", "type"], allow
            )
        with check("process"):
            check_and_get_df_from_table(conn, cursor, "process", ["pid", "process_name", "process_sort_index"], allow)
        with check("slice"):
            check_and_get_df_from_table(
                conn, cursor, "slice", ["id", "timestamp", "duration", "name", "track_id", "args", "end_time"], allow
            )
        with check("thread"):
            check_and_get_df_from_table(conn, cursor, "thread", ["tid", "pid", "thread_name", "track_id"], allow)

        with check("batch"):
            check_and_get_df_from_table(conn, cursor, "batch", ["name", "res_list", "batch_size", "batch_type"], allow)
        with check("batch_exec"):
            check_and_get_df_from_table(conn, cursor, "batch_exec", ["batch_id", "event", "pid", "start", "end"], allow)
        with check("batch_req"):
            check_and_get_df_from_table(
                conn, cursor, "batch_req", ["req_id", "iter", "rid", "block", "batch_id"], allow
            )
        with check("request"):
            check_and_get_df_from_table(
                conn, cursor, "request", ["http_rid", "recv_token_size", "reply_token_size"], allow
            )
        with check("data_table"):
            check_and_get_df_from_table(conn, cursor, "data_table", ["id", "name", "view_name"], allow)

        for view in CURVE_VIEW_NAME_LIST_COMPETITION.values():
            check_view_exists(cursor, view)


def common_csv_check(csv_path, expect_columns, expect_length=None):
    # 输出csv路径 校验路径是否存在 csv表格columns是否和输入匹配 表格长度是否和输入匹配
    csv_exist = os.path.exists(csv_path)
    assert csv_exist, f"csv_path: {csv_path} not exist"
    if not csv_exist:
        return

    df = pd.read_csv(csv_path)
    csv_columns = list(df.columns)
    assert csv_columns == expect_columns, f"columns in csv:{csv_columns} " \
                         f"not match expect_columns:{expect_columns}"

    if expect_length:
        assert len(df) == expect_length, f"csv_length:{len(df)} " \
                             f"not match expect_length:{expect_length}"


def common_db_table_check(db_path, table_name, sql_query, expect_columns, expect_length=None):
    # 输出db路径 校验路径是否存在 使用sql query从db中读取特定table 校验该table的columns是否和输入匹配 长度是否和输入匹配
    db_exist = os.path.exists(db_path)
    assert db_exist, f"csv_path: {db_path} not exist"
    if not db_exist:
        return

    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(sql_query, conn)
    except Exception as e:
        pytest.fail(f"Read db file from path:{db_path} failed.\n"
                              f"Sql_query is {sql_query}.\n"
                              f"Error message is {e}")

    table_columns = list(df.columns)
    assert table_columns == expect_columns, f"columns in db table {table_name}:{table_columns} " \
                         f"not match expect_columns:{expect_columns}"

    if expect_length:
        table_length = len(df)
        assert table_length == expect_length, f"db table {table_name} length:{table_length} " \
                             f"not match expect_length:{expect_length}"


def common_csv_match_db_table_check(db_path, csv_path, table_name, sql_query, sample_nums):
    # 输入db csv路径 使用sql_query从db中读取数据 随机挑选sample_nums个行 校验两边是否一致
    # 该函数中不进行文件存在、读取是否成功校验 应当提前使用_common_db_table_check和_common_csv_check进行校验

    with sqlite3.connect(db_path) as conn:
        csv_df = pd.read_csv(csv_path)
        db_df = pd.read_sql_query(sql_query, conn)

        assert len(csv_df) == len(db_df), f"db file:{db_path} table:{table_name} length not match csv_file:{csv_path}"

        for _ in range(sample_nums):
            random_num = random.randint(0, len(csv_df) - 1)
            assert list(csv_df.loc[random_num]) == list(db_df.loc[random_num])


def run_ep_balance_sub_test(output_path):
    with check(msg="ep_balance csv test"):
        ep_balance_csv_path = os.path.join(output_path, "ep_balance.csv")
        ep_balance_columns = ["19362", "19364", "19366", "19371", "19381", "19391", "19406", "19416"]
        common_csv_check(ep_balance_csv_path, ep_balance_columns)

    with check("ep balance db test"):
        ep_balance_db_path = os.path.join(output_path, "profiler.db")
        ep_balance_query = """
            SELECT * FROM ep_balance
        """
        common_db_table_check(ep_balance_db_path, "ep_balance", ep_balance_query, ep_balance_columns)

    with check("ep_balance db csv match test"):
        common_csv_match_db_table_check(ep_balance_db_path,
                                              ep_balance_csv_path,
                                              "ep_balance",
                                              ep_balance_query,
                                              10)

    with check("ep_balance png check"):
        ep_balance_png_path = os.path.join(output_path, "ep_balance.png")
        assert os.path.exists(ep_balance_png_path)
        assert os.path.isfile(ep_balance_png_path)


def run_moe_analysis_test(output_path):
    with check("moe_analysis csv test"):
        moe_analysis_path = os.path.join(output_path, "moe_analysis.csv")
        moe_analysis_columns = ["Dataset", "Mean", "CI_Lower", "CI_Upper"]
        common_csv_check(moe_analysis_path, moe_analysis_columns)

    with check("moe_analysis db test"):
        moe_analysis_db_path = os.path.join(output_path, "profiler.db")
        moe_analysis_query = """
            SELECT * FROM moe_analysis
        """
        common_db_table_check(moe_analysis_db_path, "moe_analysis", moe_analysis_query, moe_analysis_columns)

    with check("moe_analysis png check"):
        moe_analysis_png_path = os.path.join(output_path, "moe_analysis.png")
        assert os.path.exists(moe_analysis_png_path)
        assert os.path.isfile(moe_analysis_png_path)