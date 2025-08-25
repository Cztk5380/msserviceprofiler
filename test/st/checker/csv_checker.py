from pytest_check import check
import os
import pandas as pd
from test.st.checker.checker_utils import check_df_col_has_no_nan_value, check_df_col_has_value
from test.st.checker.checker_utils import check_df_has_no_empty_line, check_df_expected_column


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
            "start_time(ms)",
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
            "start_time(ms)",
            "end_time(ms)",
            "batch_size",
            "batch_type",
            "during_time(ms)",
        ]

        # 表头
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)

        # 每列是否有值
        check_df_col_has_no_nan_value(df, "name")
        check_df_col_has_no_nan_value(df, "res_list")
        check_df_col_has_no_nan_value(df, "start_time(ms)")
        check_df_col_has_no_nan_value(df, "end_time(ms)")
        check_df_col_has_no_nan_value(df, "batch_size")
        check_df_col_has_no_nan_value(df, "batch_type")
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

        expected_header = ["domain", "rid", "timestamp(ms)", "name", "device_kvcache_left"]

        # 表头
        check_df_expected_column(df, expected_header)

        # 没有空行
        check_df_has_no_empty_line(df)

        # 每列是否有值
        check_df_col_has_no_nan_value(df, "name")
        check_df_col_has_no_nan_value(df, "timestamp(ms)")
        check_df_col_has_no_nan_value(df, "rid")
        check_df_col_has_no_nan_value(df[df["name"] != "allocate"], "device_kvcache_left")

        # 检查事件出现次数
        if complete_req_cnt:
            check_df_col_has_value(df, "name", "Free", complete_req_cnt, empty_enable=(complete_req_cnt == 0))
            check_df_col_has_value(df, "name", "Allocate", complete_req_cnt, empty_enable=(complete_req_cnt == 0))
            check_df_col_has_value(df, "name", "AppendSlot", empty_enable=(complete_req_cnt == 0))


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
