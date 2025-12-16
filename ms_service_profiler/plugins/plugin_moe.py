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
            logger.warning("communication data is None when processing moe slow_rank analysis.")
            return data
        if communication_df.empty:
            logger.warning("communication data is empty when processing moe slow_rank analysis.")
            return data

        distribute_df = communication_df[(communication_df["name"] == MOE_DISTRIBUTED_COMBINE) | (
                    communication_df["name"] == MOE_DISTRIBUTED_DISPATCH)]

        if distribute_df.empty:
            logger.warning(f"no {MOE_DISTRIBUTED_DISPATCH} or {MOE_DISTRIBUTED_COMBINE} found in communication data.")
            return data

        confidence_intervals = []

        for db_id, grouped_df in distribute_df.groupby("db_id"):
            start_time_arr = grouped_df["start"].values
            end_time_arr = grouped_df["end"].values
            duration_arr = end_time_arr - start_time_arr
            n = duration_arr.size

            if n == 0:
                raise ZeroDivisionError(f"Cannot calculate standard error: sample size n must be positive (got n={n})")

            mean = duration_arr.mean().mean()
            std = duration_arr.std()
            se = std / np.sqrt(n)

            # 95置信区间
            margin_of_error = stats.t.ppf(0.975, df=n - 1) * se  # t分布的临界值
            ci_lower = mean - margin_of_error
            ci_upper = mean + margin_of_error

            confidence_intervals.append((db_id, mean, ci_lower, ci_upper))
        ci_df = pd.DataFrame(confidence_intervals, columns=["Dataset", "Mean", "CI_Lower", "CI_Upper"])
        data["moe_analysis"] = ci_df
        return data
