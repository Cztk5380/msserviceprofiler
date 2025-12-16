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

from .utils import logger
from .constants import US_PER_MS

CSV_COLUMNS = ["name", "during_time", "pid", "tid", "start_time", "end_time", "rid", "start_datetime", 
               "end_datetime", "batch_type", "batch_size", "rid_list", "token_id_list"]

RENAMED_COLUMNS = {
        "start_time": "start_time(ms)",
        "end_time": "end_time(ms)",
        "during_time": "during_time(ms)"
    }

PREFILL_NAME = "Prefill"
DECODE_NAME = "Decode"


def get_statistics_data(framework_df, filter_name, name):
    if framework_df.empty:
        logger.warning(f"{name}: The dataframe is empty, no csv file create")
        return framework_df
    
    time_columns = {
        "during_time(ms)": lambda x: x / US_PER_MS,
        "start_time(ms)": lambda x: x // US_PER_MS,
        "end_time(ms)": lambda x: x // US_PER_MS
    }

    # 批量转换时间单位
    for col, func in time_columns.items():
        if col in framework_df.columns:
            framework_df[col] = func(framework_df[col])
        else:
            logger.warning(f"Column '{col}' not found for time conversion.")

    mask = framework_df["name"] == filter_name
    if not mask.any():
        logger.warning(f"'{filter_name}' not found in the dataframe.")
        return framework_df
    filter_indices = framework_df[mask].index
    if len(filter_indices) == 1:
        start_index = filter_indices[-1]
        end_index = None
    else:
        max_interval_index = max(
            range(len(filter_indices) - 1),
            key=lambda i: filter_indices[i + 1] - filter_indices[i]
        )
        start_index = filter_indices[max_interval_index]
        end_index = filter_indices[max_interval_index + 1] - 1
    stats = ["max", "min", "mean", "std"]
    grouped = framework_df.groupby("name")["during_time(ms)"]
    for stat in stats:
        framework_df[stat] = grouped.transform(stat)
    # 处理标准差为 NaN 的情况
    framework_df["std"] = framework_df["std"].fillna(0)
    # 重新排列列顺序
    for idx, stat in enumerate(stats, start=2):
        framework_df.insert(idx, stat, framework_df.pop(stat))
    
    col_limit = 10 if name == DECODE_NAME else 11
    framework_df = framework_df.iloc[:, :col_limit]

    return framework_df[start_index: end_index]


def get_service_type(framework_df):
    from ..split_processor import VllmProcessor, MindIEProcessor, MindIEProcessorV2
    result_service = MindIEProcessor()
    name_set = set(list(framework_df["name"]))
    if "deserializeExecuteResponse" not in name_set:
        if "SerializeRequests" in name_set:
            result_service = MindIEProcessorV2()
        else:
            result_service = VllmProcessor()
    return result_service