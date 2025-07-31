# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import (
    write_result_to_csv, write_result_to_db, check_domain_valid
)
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer


REQUIED_NAME = set(["forward"])
REMAME_COLUMNS = {
    "start_time": "start_time(ms)",
    "end_time": "end_time(ms)",
    "during_time": "during_time(ms)"
}
DELETE_COLUMNS = ["rid", "rid_list", "pid", "tid"]


class ExporterForwardData(ExporterBase):
    name = "forward_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args
    
    @classmethod
    @timer(logger.info)
    def export(cls, data) -> None:
        if "csv" not in cls.args.format and "db" not in cls.args.format:
            return
        
        df = data.get("tx_data_df")
        if df is None:
            logger.warning("The data is empty, please check")
            return
        output = cls.args.output_path

        if check_domain_valid(df, ["ModelExecute", "BatchSchedule", "Schedule"], "forward") is False:
            return
        # 取出 forward 和 batch_start_name
        batch_name = get_batch_name(df)
        REQUIED_NAME.add(batch_name)
        check_all = all(element in df["name"].unique() for element in REQUIED_NAME)
        if not check_all:
            logger.warning(f"The data is not complete, please check. \
                            The required data for forward.csv is {REQUIED_NAME}")
            return

        forward_df = get_filter_forward_df(REQUIED_NAME, df)
        
        # 获取batch_type 和 batch_size
        forward_df = get_batch_info(forward_df, batch_name)
        
        # 计算 relative_time, bubble_time
        forward_df = get_relative_and_bubble(forward_df)
        
        forward_df = forward_df.drop(columns=DELETE_COLUMNS)
        forward_df["forward_iter"] = forward_df.groupby("prof_id").cumcount() + 1
        forward_df = forward_df.sort_values(by=["start_time"]).reset_index(drop=True)

        if 'db' in cls.args.format:
            write_result_to_db(
                df_param_list=[[forward_df, "forward"]],
                table_name="forward",
                rename_cols=REMAME_COLUMNS
            )

        if 'csv' in cls.args.format:
            write_result_to_csv(forward_df, output, "forward", REMAME_COLUMNS)


# 按 hostname 分组，并计算每个分组的相对时间
def calculate_relative_times(group):
    base_time = group["start_time"].min()  # 以每个分组中的最小 start_time 为基准时间
    group["relative_start_time(ms)"] = (group["start_time"] - base_time).round(2)
    return group


def calculate_bubble_time(group):
    group["bubble_time(ms)"] = (group["start_time"].shift(-1) - group["end_time"]).round(2)
    return group


def get_batch_name(dataframe):
    batch_name = ""
    if (dataframe["name"] == "BatchSchedule").any():
        batch_name = "BatchSchedule"
    elif (dataframe["name"] == "batchFrameworkProcessing").any():
        batch_name = "batchFrameworkProcessing"
    else:
        batch_name = "Schedule"
    return batch_name


def get_filter_forward_df(required_name, forward_df):
    # copy 消除pandas警告
    filter_df = forward_df[forward_df["name"].isin(required_name)].copy()

    ori_columns = ["name", "relative_start_time(ms)", "start_time", "end_time",
                    "during_time", "bubble_time(ms)", "batch_size", "batch_type",
                    "forward_iter", "rid", "rid_list", "dp_rank", "prof_id", "hostname",
                    "pid", "tid"]
    
    missing_columns = set(ori_columns) - set(forward_df.columns)
    for col in missing_columns:
        filter_df[col] = None
    convert_time_cols = ["during_time", "start_time", "end_time"]
    filter_df[convert_time_cols] = filter_df[convert_time_cols].div(US_PER_MS)

    filter_df = filter_df.reindex(columns=ori_columns)

    return filter_df


def get_batch_info(forward_df, batch_name):
    if forward_df[["batch_type", "batch_size"]].notna().all().all():
        return forward_df[forward_df["name"] != batch_name]
    # 按rid分组forward_df
    forward_df_grouped = forward_df.groupby("rid")

    merged = pd.DataFrame(columns=forward_df.columns)

    # 遍历每组rid
    for _, group in forward_df_grouped:
        temp_result = group.copy()
        
        batch_name_indices = group[group['name'] == batch_name].index
        if len(batch_name_indices) == 0:
            continue

        for idx in batch_name_indices:
            temp_result.loc[(temp_result.index > idx), 'batch_type'] = group.loc[idx, 'batch_type']
        
        # 将处理后的组添加到最终结果中
        merged = pd.concat([merged, temp_result], ignore_index=True)

    mask = (merged["name"] != batch_name)
    merged = merged[mask].sort_values(by=["start_time"]).reset_index(drop=True)

    return merged


def get_relative_and_bubble(forward_df):
    forward_df = forward_df.groupby("hostname").apply(calculate_relative_times).reset_index(drop=True)
    # 计算 bubble_time
    forward_df = forward_df.groupby("prof_id").apply(calculate_bubble_time).reset_index(drop=True)
    mask = forward_df.groupby(["prof_id", "pid"]).cumcount(ascending=False) == 0
    forward_df.loc[mask, "bubble_time(ms)"] = pd.NA

    return forward_df