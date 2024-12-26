# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import datetime
import psutil

from ms_service_profiler.constant import US_PER_SECOND
from ms_service_profiler.plugins.base import PluginBase


class PluginTimeStampHelper(PluginBase):
    name = "plugin_timestamp_helper"
    depends = []

    @classmethod
    def parse(cls, data):
        tx_data_df = data.get('tx_data_df')
        cpu_data_df = data.get('cpu_data_df')
        time_info = data.get('time_info')
        
        if time_info is None:
            raise ValueError("There is no time infomation, please check data.")
        
        sys_start_cnt = time_info.get('sys_start_cnt')
        cpu_start_cnt = time_info.get('cpu_start_cnt')
        if sys_start_cnt is None:
            raise ValueError("sys_start_cnt is None, please check data.")
        if cpu_start_cnt is None:
            raise ValueError("cpu_start_cnt is None, please check data.")
        
        requested_col = ['start_time', 'end_time']
        if tx_data_df is not None:
            for column_name in requested_col:
                if column_name not in tx_data_df.columns:
                    raise KeyError(f'{column_name} not found. Timestamp parsing failed.')
            tx_data_df['start_time'] = convert_syscnt_to_ts(tx_data_df['start_time'], sys_start_cnt, time_info)
            tx_data_df['end_time'] = convert_syscnt_to_ts(tx_data_df['end_time'], sys_start_cnt, time_info)
            tx_data_df['during_time'] = tx_data_df['end_time'] - tx_data_df['start_time']
            tx_data_df['start_datetime'] = tx_data_df['start_time'].apply(timestamp_converter)
            tx_data_df['end_datetime'] = tx_data_df['end_time'].apply(timestamp_converter)

        if cpu_data_df is not None:
            for column_name in requested_col:
                if column_name not in cpu_data_df.columns:
                    raise KeyError(f'{column_name} not found. Timestamp parsing failed.')
            cpu_data_df['start_time'] = convert_syscnt_to_ts(cpu_data_df['start_time'], cpu_start_cnt, time_info)
            cpu_data_df['end_time'] = convert_syscnt_to_ts(cpu_data_df['end_time'], cpu_start_cnt, time_info)
            cpu_data_df['during_time'] = cpu_data_df['end_time'] - cpu_data_df['start_time']
            cpu_data_df['start_datetime'] = cpu_data_df['start_time'].apply(timestamp_converter)
            cpu_data_df['end_datetime'] = cpu_data_df['end_time'].apply(timestamp_converter)

        data = {
            'tx_data_df': tx_data_df,
            'cpu_data_df': cpu_data_df,
        }
        return data


class PluginTimeStamp(PluginBase):
    name = "plugin_timestamp"
    depends = []
    helper = PluginTimeStampHelper()

    @classmethod
    def parse(cls, data):
        res = []
        for data_single in data:
            res.append(cls.helper.parse(data_single))
        return res


def convert_syscnt_to_ts(cnt, start_cnt, time_info):
    cpu_frequency = time_info.get('cpu_frequency')
    sys_start_time = time_info.get('sys_start_time')
    try:
        return (sys_start_time + ((cnt - start_cnt) / cpu_frequency)) * US_PER_SECOND
    except Exception as ex:
        raise AttributeError("Timestamp format error.") from ex


def timestamp_converter(timestamp):
    date_time = datetime.datetime.fromtimestamp(timestamp / US_PER_SECOND)
    return date_time.strftime("%Y-%m-%d %H:%M:%S:%f")
