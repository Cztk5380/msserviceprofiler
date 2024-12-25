# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import datetime
import psutil

from ms_service_profiler.constant import US_PER_SECOND
from ms_service_profiler.plugins.base import PluginBase


SYS_TS = psutil.boot_time()


class PluginTimeStamp(PluginBase):
    name = "plugin_timestamp"
    depends = []

    @classmethod
    def parse(cls, data):
        tx_data_df = data.get('tx_data_df')
        cpu_data_df = data.get('cpu_data_df')
        cpu_start_cnt = data.get('cpu_start_cnt')
        cpu_frequency = data.get('cpu_frequency')
        sys_start_cnt = data.get('sys_start_cnt')
        
        tx_data_df['start_time'] = convert_syscnt_to_ts(tx_data_df['start_time'], sys_start_cnt, cpu_frequency)
        tx_data_df['end_time'] = convert_syscnt_to_ts(tx_data_df['end_time'], sys_start_cnt, cpu_frequency)
        tx_data_df['start_datatime'] = tx_data_df['start_time'].apply(timestamp_converter)
        tx_data_df['end_datatime'] = tx_data_df['end_time'].apply(timestamp_converter)
        tx_data_df['during_time'] = tx_data_df['end_time'] - tx_data_df['start_time']
        

        cpu_data_df['start_time'] = convert_syscnt_to_ts(cpu_data_df['start_time'], cpu_start_cnt, cpu_frequency)
        cpu_data_df['end_time'] = convert_syscnt_to_ts(cpu_data_df['end_time'], cpu_start_cnt, cpu_frequency)
        cpu_data_df['start_datatime'] = cpu_data_df['start_time'].apply(timestamp_converter)
        cpu_data_df['end_datatime'] = cpu_data_df['end_time'].apply(timestamp_converter)
        cpu_data_df['during_time'] = cpu_data_df['end_time'] - cpu_data_df['start_time']

        data['cpu_data_df'] = cpu_data_df
        data['tx_data_df'] = tx_data_df
        return data


def convert_syscnt_to_ts(cnt, start_cnt, cpu_frequency):
    try:
        return (SYS_TS + ((cnt - start_cnt) / cpu_frequency)) * US_PER_SECOND
    except Exception as ex:
        raise AttributeError("Timestamp format error.") from ex


def timestamp_converter(timestamp):
    date_time = datetime.datetime.fromtimestamp(timestamp / US_PER_SECOND)
    return date_time.strftime("%Y-%m-%d %H:%M:%S:%f")
