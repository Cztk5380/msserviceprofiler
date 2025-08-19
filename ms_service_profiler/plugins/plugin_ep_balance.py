# Copyright Huawei Technologies Co., Ltd. 2025-2025. All rights reserved.
import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger


GROUPED_MATMUL_API_NAME = "aclnnGroupedMatmulV4_GroupedMatmul_GroupedMatmul"
GMM_NUM_PER_LAYER = 2
DEEPSEEK_MOE_DECODER_LAYER_NUMS = 58


class PluginEpBalanceProcess(PluginBase):
    name = "plugin_ep_balance_process"

    @classmethod
    def parse(cls, data):
        kernel_df = data.get("kernel_df")
        if kernel_df is None:
            logger.warning("kernel data is None when processing ep_balance analysis.")
            return data
        if kernel_df.empty:
            logger.warning("kernel data is empty when processing ep_balance analysis.")
            return data

        grouped_matmul_df = kernel_df[kernel_df["name"] == GROUPED_MATMUL_API_NAME]

        if grouped_matmul_df.empty:
            logger.warning(f"no {GROUPED_MATMUL_API_NAME} found in kernel_df.")
            return data

        res_dic = {}

        for db_id, df_group_by_pid in grouped_matmul_df.groupby("db_id"):
            start_time_arr = df_group_by_pid["start"].values
            end_time_arr = df_group_by_pid["end"].values
            duration_arr = end_time_arr - start_time_arr

            if len(duration_arr) % GMM_NUM_PER_LAYER != 0:
                logger.warning(f"grouped matmul nums error {len(duration_arr)}")
                duration_arr = duration_arr[:-1]

            duration_arr = sum([duration_arr[i::GMM_NUM_PER_LAYER] for i in range(GMM_NUM_PER_LAYER)])

            # 后续改为从api中获取num_layers
            res_dic[db_id] = group_gmm_by_decoder_layer(duration_arr, DEEPSEEK_MOE_DECODER_LAYER_NUMS)

        res_df = pd.DataFrame.from_dict(res_dic)
        data["ep_balance"] = res_df

        return data


def group_gmm_by_decoder_layer(duration_arr, num_layers):
    if num_layers > 0:
        ep_balance_per_layer = []
        for i in range(num_layers):
            ep_balance = np.sum(duration_arr[i::num_layers])
            ep_balance_per_layer.append(ep_balance)
        return ep_balance_per_layer
    return duration_arr
