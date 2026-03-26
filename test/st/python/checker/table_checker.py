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

from pytest_check import check
import os
import sqlite3
from contextlib import contextmanager, ExitStack

import pandas as pd
from ms_service_profiler.exporters.utils import CURVE_VIEW_NAME_LIST_COMPETITION
from checker.checker_utils import check_df_has_no_empty_line, check_df_expected_column


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
        expected_header = ["p50", "p90", "p99", "timestamp", "p50_alltime"]
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
            expected_header = ["name", "start_datetime", "kvcache_usage_rate"]
            check_and_get_df_from_table(conn, cursor, table_name, expected_header, complete_req_cnt == 0)


def check_sglang_db_tables(conn, complete_req_cnt=0):
    """SGLang 场景下校验 profiler.db：kvcache 表及 insight 相关表（counter/flow/process/slice/thread/batch/request/data_table）"""
    allow = complete_req_cnt == 0
    with sqlite_cursor(conn) as cursor:
        with check("kvcache"):
            check_and_get_df_from_table(
                conn, cursor, "kvcache",
                ["name", "start_datetime", "total_blocks", "kvcache_usage_rate"],
                allow,
            )
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
        with check("request"):
            check_and_get_df_from_table(
                conn, cursor, "request", ["http_rid", "recv_token_size", "reply_token_size"], allow
            )
        with check("data_table"):
            check_and_get_df_from_table(conn, cursor, "data_table", ["id", "name", "view_name"], allow)


def check_req_status_table(conn, complete_req_cnt=0):
    table_name = "request_status"
    with sqlite_cursor(conn) as cursor:
        with check(table_name):
            # 表头
            expected_header = ["timestamp", "QueueSize=", "status"]
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
