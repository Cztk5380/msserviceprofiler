# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger


GROUPED_MATMUL_API_NAME = "aclnnGroupedMatmulV4_GroupedMatmul_GroupedMatmul"
GMM_NUM_PER_LAYER = 2


class PluginEpBalanceProcess(PluginBase):
    name = "plugin_ep_balance_process"

    @classmethod
    def parse(cls, data):
        if check_df_empty(data, "kernel_df"):
            kernel_df = data.get("kernel_df")
            grouped_matmul_df = kernel_df[kernel_df["name"] == GROUPED_MATMUL_API_NAME]

            res_dic = {}

            for db_id, df_group_by_pid in grouped_matmul_df.groupby("processId"):
                start_time_arr = df_group_by_pid["start"]
                end_time_arr = df_group_by_pid["end"]
                duration_arr = end_time_arr - start_time_arr

                if len(duration_arr) % GMM_NUM_PER_LAYER != 0:
                    logger.warning("grouped matmul nums error")
                    duration_arr = duration_arr[:-1]

                duration_arr = np.sum([duration_arr[i::GMM_NUM_PER_LAYER] for i in range(GMM_NUM_PER_LAYER)])

                num_layers = 58
                if num_layers > 0:
                    ep_balance_per_layer = []
                    for i in range(num_layers):
                        ep_balance = np.sum(duration_arr[i::num_layers])
                        ep_balance_per_layer.append(ep_balance)
                    res_dic[db_id] = ep_balance_per_layer
                else:
                    res_dic[db_id] = duration_arr
            res_df = pd.DataFrame.from_dict(res_dic)
            data["ep_balance"] = res_df

        return data


def check_df_empty(df_dict, key):
    if key not in df_dict.keys():
        return False
    df = df_dict[key]
    if df.empty:
        return False
    return True
