# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import pandas as pd
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger


class PluginMsptiProcess(PluginBase):
    name = "plugin_mspti_process"

    @staticmethod
    def _process(api_df, kernel_df):
        renamed_kernel = replace_name(kernel_df, api_df)
        return renamed_kernel

    @classmethod
    def parse(cls, data):
        mspti_api_list = []
        mspti_kernel_list = []

        for item in data:
            if check_df_empty(item, "api_df") and check_df_empty(item, "kernel_df"):
                renamed_kernel = cls._process(item["api_df"], item["kernel_df"])
                mspti_api_list.append(item["api_df"])
                mspti_kernel_list.append(renamed_kernel)
            else:
                logger.warning("No mspti data detected in certain db, skipping process.")

        if mspti_kernel_list and mspti_kernel_list:
            concated_api_df = pd.concat(mspti_api_list)
            concated_kernel_df = pd.concat(mspti_kernel_list)
            return dict(
                api_df=concated_api_df,
                kernel_df=concated_kernel_df
            )
        else:
            logger.warning("No data found in all ascend_service_profiler_*.db, skipping parse.")
            return None


def replace_name(df1, df2):
    # 创建cor_id到name的映射字典（保留df2最后一个重复值）
    name_mapping = df2.drop_duplicates(subset='correlationId', keep='first').set_index('correlationId')['name']

    # 用df2的name替换df1的name（当cor_id匹配时）
    df1['new_name'] = df1['correlationId'].map(name_mapping)
    df1['name'] = df1['new_name'].fillna(df1['name'])
    # 删除临时列
    df1.drop(columns=['new_name'], inplace=True)
    return df1


def check_df_empty(df_dict, key):
    if key not in df_dict.keys():
        return False
    df = df_dict[key]
    if df.empty:
        return False
    return True
