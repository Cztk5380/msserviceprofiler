# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger
from scipy import stats
import matplotlib.pyplot as plt

MOE_DISTRIBUTED_COMBINE = "MoeDistributeCombine"
MOE_DISTRIBUTED_DISPATCH = "MoeDistributeDispatch"


class PluginMoeSlowRankProcess(PluginBase):
    name = "plugin_moe_slow_rank_process"

    @classmethod
    def parse(cls, data):
        if check_df_empty(data, "communication_df"):
            communication_df = data.get("communication_df")
            distribute_df = communication_df[(communication_df["name"] == MOE_DISTRIBUTED_COMBINE) | (
                        communication_df["name"] == MOE_DISTRIBUTED_DISPATCH)]

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


