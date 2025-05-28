# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger


MOE_DISTRIBUTED_COMBINE = "MoeDistributeCombine"
MOE_DISTRIBUTED_DISPATCH = "MoeDistributeDispatch"


class PluginMoeSlowRankProcess(PluginBase):
    name = "plugin_moe_slow_rank_process"

    @classmethod
    def parse(cls, data):
        if check_df_empty(data, "communication_df"):
            communication_df = data.get("communication_df")
            combine_df = communication_df[communication_df["name"] == MOE_DISTRIBUTED_COMBINE]
            dispatch_df = communication_df[communication_df["name"] == MOE_DISTRIBUTED_DISPATCH]



        return data


def check_df_empty(df_dict, key):
    if key not in df_dict.keys():
        return False
    df = df_dict[key]
    if df.empty:
        return False
    return True