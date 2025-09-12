# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from collections import defaultdict

import pandas as pd

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger


class PluginConcat(PluginBase):
    name = "plugin_concat"
    depends = ["plugin_timestamp"]

    @staticmethod
    def _merge_msprof_data(data):
        """合并 msprof_data 数据"""
        msprof_merged = []
        for data_single in data:
            value = data_single.get("msprof_data")
            if isinstance(value, list):
                msprof_merged.extend(value)
            elif value is not None:
                msprof_merged.append(value)
        return msprof_merged

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        merged_data = defaultdict(pd.DataFrame)
        merge_list = defaultdict(list)

        for data_single in data:
            for key, value in data_single.items():
                if isinstance(value, pd.DataFrame):
                    merge_list[key].append(value)

        for key, df_list in merge_list.items():
            merged_data[key] = pd.concat(df_list, ignore_index=True)

        msprof_merged = cls._merge_msprof_data(data)

        if msprof_merged:
            merged_data["msprof_data"] = msprof_merged

        # 避免丢失 pid_label_map
        pid_label_map = {}
        for data_single in data:
            if 'pid_label_map' in data_single and data_single['pid_label_map'] is not None:
                if isinstance(data_single['pid_label_map'], dict):
                    pid_label_map.update(data_single['pid_label_map'])

        if pid_label_map:
            merged_data["pid_label_map"] = pid_label_map

        for key, value in merged_data.items():
            if isinstance(value, pd.DataFrame):
                merged_data[key] = value.sort_values(by='start_time', ascending=True).reset_index(drop=True)

        return merged_data

