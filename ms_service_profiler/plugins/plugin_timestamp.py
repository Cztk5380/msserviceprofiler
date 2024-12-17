# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
        tx_data_df['during_time'] = tx_data_df['end_time'] - tx_data_df['start_time']

        cpu_data_df['start_time'] = convert_syscnt_to_ts(cpu_data_df['start_time'], cpu_start_cnt, cpu_frequency)
        cpu_data_df['end_time'] = convert_syscnt_to_ts(cpu_data_df['end_time'], cpu_start_cnt, cpu_frequency)
        cpu_data_df['during_time'] = cpu_data_df['end_time'] - cpu_data_df['start_time']

        data['cpu_data_df'] = cpu_data_df
        data['tx_data_df'] = tx_data_df
        return data


def convert_syscnt_to_ts(cnt, start_cnt, cpu_frequency):
    return (SYS_TS + ((cnt - start_cnt) / cpu_frequency)) * US_PER_SECOND