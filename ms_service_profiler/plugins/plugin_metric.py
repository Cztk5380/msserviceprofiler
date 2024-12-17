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

import pandas as pd
from ms_service_profiler.plugins.base import PluginBase


class PluginMetric(PluginBase):
    name = "plugin_metric"
    depends = ["plugin_common", "plugin_req_status", "plugin_timestamp"]

    @classmethod
    def parse(cls, data):
        tx_data_df = data.get('tx_data_df')
        if tx_data_df is None:
            raise ValueError("tx_data_df is None")
        
        columns = [metric for metric in tx_data_df.columns if metric.startswith('+') or metric.startswith('=')]

        tx_data_df['metrics'] = tx_data_df[columns].apply(
            lambda row: {col: row[col] for col in columns if row[col] is not None}, axis=1).apply(
            lambda x: None if x == {} else x)        
        
        metric_data_df = pd.concat([tx_data_df[['start_time', 'metrics'] + columns]], axis=1)
        metric_data_df = metric_data_df.query("metrics == metrics")
        metric_data_df = metric_data_df.rename(columns={'start_time': 'time'})
        
        data['tx_data_df'] = tx_data_df
        data['metric_data_df'] = metric_data_df[['time', 'metrics']]
        data['metric_data_details_df'] = metric_data_df
        return data


