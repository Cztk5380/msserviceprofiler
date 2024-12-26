# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from collections import defaultdict

import pandas as pd

from ms_service_profiler.plugins.base import PluginBase


class PluginConcat(PluginBase):
    name = "plugin_concat"
    depends = ["plugin_timestamp"]

    @classmethod
    def parse(cls, data):
        merged_data = defaultdict(pd.DataFrame)
        for data_single in data:
            for key, value in data_single.items():
                if isinstance(value, pd.DataFrame):
                    merged_data[key] = pd.concat([merged_data[key], value], ignore_index=True)
        for key, value in merged_data.items():
            merged_data[key] = value.sort_values(by='start_time', ascending=True).reset_index(drop=True)
        return merged_data
