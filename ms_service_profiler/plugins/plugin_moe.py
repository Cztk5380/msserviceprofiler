# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import pandas as pd
import numpy as np
from scipy import stats
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger

MOE_DISTRIBUTED_COMBINE = "MoeDistributeCombine"
MOE_DISTRIBUTED_DISPATCH = "MoeDistributeDispatch"


class PluginMoeSlowRankProcess(PluginBase):
    name = "plugin_moe_slow_rank_process"

    @classmethod
    def parse(cls, data):
        communication_df = data.get("communication_df")
        if communication_df is None:
            logger.warning("communication_df is None when processing moe slow_rank analysis.")
            return data
        if communication_df.empty:
            logger.warning("communication_df is empty when processing moe slow_rank analysis.")
            return data

        distribute_df = communication_df[(communication_df["name"] == MOE_DISTRIBUTED_COMBINE) | (
                    communication_df["name"] == MOE_DISTRIBUTED_DISPATCH)]

        if distribute_df.empty:
            logger.warning(f"no {MOE_DISTRIBUTED_DISPATCH} or {MOE_DISTRIBUTED_COMBINE} found in communication_df.")
            return data

        confidence_intervals = []

        for db_id, grouped_df in distribute_df.groupby("db_id"):
            mean = grouped_df.mean().mean()
            std = grouped_df.stack().std()
            n = grouped_df.size

            se = std / np.sqrt(n)

            # 95置信区间
            margin_of_error = stats.t.ppf(0.975, df=n - 1) * se  # t分布的临界值
            ci_lower = mean - margin_of_error
            ci_upper = mean + margin_of_error

            confidence_intervals.append((db_id, mean, ci_lower, ci_upper))
        ci_df = pd.DataFrame(confidence_intervals, columns=["Dataset", "Mean", "CI_Lower", "CI_Upper"])
        data["moe_analysis"] = ci_df
        return data


def check_df_empty(df_dict, key):
    if key not in df_dict.keys():
        return False
    df = df_dict[key]
    if df.empty:
        return False
    return True


