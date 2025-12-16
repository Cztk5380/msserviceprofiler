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
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger


class PluginMsptiProcess(PluginBase):
    name = "plugin_mspti_process"

    @classmethod
    def parse(cls, data):
        mspti_api_list = []
        mspti_kernel_list = []
        mspti_communication_list = []

        for item in data:
            if check_df_empty(item, "api_df") and check_df_empty(item, "kernel_df"):
                renamed_kernel = replace_name(item["kernel_df"], item["api_df"])
                mspti_api_list.append(item["api_df"])
                mspti_kernel_list.append(renamed_kernel)
            else:
                logger.warning("No api data or kernel data detected in certain db, skipping process.")

            if check_df_empty(item, "communication_df"):
                mspti_communication_list.append(item["communication_df"])
        res = {}

        if mspti_kernel_list and mspti_kernel_list:
            api_df = pd.concat(mspti_api_list)
            kernel_df = pd.concat(mspti_kernel_list)
            res["api_df"] = api_df
            res["kernel_df"] = kernel_df

        if mspti_communication_list:
            communication_df = pd.concat(mspti_communication_list)
            res["communication_df"] = communication_df

        if res:
            return res

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
