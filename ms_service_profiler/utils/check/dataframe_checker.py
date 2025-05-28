# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import pandas as pd


def check_df_empty(df_dict, key):
    if key not in df_dict.keys():
        return False
    df = df_dict[key]
    if df.empty:
        return False
    return True
