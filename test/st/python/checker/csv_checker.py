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
import pandas as pd

from pathlib import Path
from checker.checker_utils import check_df_col_has_no_nan_value, check_df_col_has_value
from checker.checker_utils import check_df_has_no_empty_line, check_df_expected_column
from checker.checker_utils import check_df_col_unique_value_nums


def check_req_csv(output_path, complete_req_cnt=0):
    csv_file_path = f"{output_path}/request.csv"
    with check(f"check[{csv_file_path}]"):
        # 是否存在
        assert os.path.exists(csv_file_path), f"{csv_file_path} is not exists"

        df = pd.read_csv(csv_file_path)

        # 是否为空
        assert len(df) > 0, f"{csv_file_path} is empty."

        # 表头
        expected_header = [
            "http_rid",
            "start_datetime",
            "recv_token_size",
            "reply_token_size",
            "execution_time(ms)",
            "queue_wait_time(ms)",
        ]
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)

        # 完整的请求数量
        if complete_req_cnt > 0:
            assert df.size == complete_req_cnt, f"request count not match. expected {complete_req_cnt}"
            # recv_token_size和 reply_token_size 是否有值
            check_df_col_has_no_nan_value(df, "recv_token_size")
            check_df_col_has_no_nan_value(df, "reply_token_size")
            # execution_time 和 queue_wait_time 是否有值
            check_df_col_has_no_nan_value(df, "execution_time(ms)")
            check_df_col_has_no_nan_value(df, "queue_wait_time(ms)")


def check_batch_csv(output_path):
    csv_file_path = f"{output_path}/batch.csv"
    with check(f"check[{csv_file_path}]"):
        # 是否存在
        assert os.path.exists(csv_file_path), f"{csv_file_path} is not exists"

        df = pd.read_csv(csv_file_path)

        # 是否为空
        assert len(df) > 0, f"{csv_file_path} is empty."

        expected_header = [
            "name",
            "res_list",
            "start_time",
            "end_time",
            "batch_size",
            "total_batch_size",
            "during_time(ms)",
        ]

        # 表头
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)

        # 每列是否有值
        check_df_col_has_no_nan_value(df, "name")
        check_df_col_has_no_nan_value(df, "res_list")
        check_df_col_has_no_nan_value(df, "start_time")
        check_df_col_has_no_nan_value(df, "end_time")
        check_df_col_has_no_nan_value(df, "total_batch_size")
        check_df_col_has_no_nan_value(df[df['batch_type'] != 'Execute'], "batch_type")
        check_df_col_has_no_nan_value(df, "during_time(ms)")


def check_kvcache_csv(output_path, complete_req_cnt=0):
    csv_file_path = f"{output_path}/kvcache.csv"
    with check(f"check[{csv_file_path}]"):
        # 是否存在
        assert os.path.exists(csv_file_path), f"{csv_file_path} is not exists"

        df = pd.read_csv(csv_file_path)

        # 是否为空
        if complete_req_cnt:
            assert len(df) > 0, f"{csv_file_path} is empty."

        expected_header = ["domain", "start_time", "name", "kvcache_usage_rate"]

        # 表头
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)

        # 每列是否有值
        check_df_col_has_no_nan_value(df, "name")
        check_df_col_has_no_nan_value(df, "start_time")
        check_df_col_has_no_nan_value(df, "total_blocks")
        check_df_col_has_no_nan_value(df, "kvcache_usage_rate")

        # 检查事件出现次数
        if complete_req_cnt:
            check_df_col_has_value(df, "name", "Free", complete_req_cnt, empty_enable=(complete_req_cnt == 0))
            check_df_col_has_value(df, "name", "Allocate", complete_req_cnt, empty_enable=(complete_req_cnt == 0))
            check_df_col_has_value(df, "name", "AppendSlot", empty_enable=(complete_req_cnt == 0))


def check_forward_csv(output_path, card_nums=0, device_nums=0):
    csv_file_path = f"{output_path}/forward.csv"
    prof_col_name = "prof_id"
    hostname_col_name = "hostname"
    relative_col_name = "relative_start_time(ms)"
    batch_size_col_name = "batch_size"
    batch_type_col_name = "batch_type"
    name_col_name = "name"
    with check(f"check[{csv_file_path}]"):
        # 是否存在
        assert os.path.exists(csv_file_path), f"{csv_file_path} is not exists"

        df = pd.read_csv(csv_file_path)

        expected_header = [name_col_name, relative_col_name, "start_time", "end_time", \
            "during_time(ms)", "bubble_time(ms)", batch_size_col_name, batch_type_col_name, \
            "forward_iter", "dp_rank", prof_col_name, hostname_col_name]

        # 表头
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)

        # 每列是否有值, 允许bubble_time(ms)有空值
        check_df_col_has_no_nan_value(df, name_col_name)
        check_df_col_has_no_nan_value(df, relative_col_name)
        check_df_col_has_no_nan_value(df, batch_size_col_name)
        check_df_col_has_no_nan_value(df, batch_type_col_name)
        check_df_col_has_no_nan_value(df, prof_col_name)
        check_df_col_has_no_nan_value(df, hostname_col_name)

        # 理论上每张卡会有一个prof_id, 每台机器会有一个hostname
        if card_nums:
            check_df_col_unique_value_nums(df, prof_col_name, card_nums)

        if device_nums:
            check_df_col_unique_value_nums(df, hostname_col_name, device_nums)


def check_pd_split_kvcache_csv(output_path, complete_req_cnt=0):
    csv_file_path = f"{output_path}/pd_split_kvcache.csv"

    with check(f"check[{csv_file_path}]"):
        # 是否存在
        assert os.path.exists(csv_file_path), f"{csv_file_path} is not exists"

        df = pd.read_csv(csv_file_path)

        # 是否为空
        if complete_req_cnt > 0:
            assert len(df) > 0, f"{csv_file_path} is empty."

        expected_header = [
            "domain",
            "rank",
            "rid",
            "block_tables",
            "batch_seq_len",
            "during_time(ms)",
            "start_datetime(ms)",
            "end_datetime(ms)",
            "start_time(ms)",
            "end_time(ms)",
        ]

        # 表头
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)


def check_pd_split_communication_csv(output_path, complete_req_cnt=0):
    csv_file_path = f"{output_path}/pd_split_communication.csv"

    with check(f"check[{csv_file_path}]"):
        # 是否存在
        assert os.path.exists(csv_file_path), f"{csv_file_path} is not exists"

        df = pd.read_csv(csv_file_path)

        # 是否为空
        if complete_req_cnt > 0:
            assert len(df) > 0, f"{csv_file_path} is empty."

        expected_header = [
            "rid",
            "http_req_time(ms)",
            "send_request_time(ms)",
            "send_request_succ_time(ms)",
            "prefill_res_time(ms)",
            "request_end_time(ms)",
        ]

        # 表头
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)


def has_op_csv_files(folder_path):
    folder = Path(folder_path)
    has_summary = False
    has_statistic = False
    
    # 使用 rglob 递归查找所有匹配的文件
    for file in folder.rglob("*.csv"):
        filename = file.name
        if filename.startswith("op_summary"):
            has_summary = True
        elif filename.startswith("op_statistic"):
            has_statistic = True
        
        # 如果两种文件都已找到，可以提前返回True
        if has_summary and has_statistic:
            return True
    
    # 如果循环结束，检查是否两种文件都存在
    return has_summary and has_statistic