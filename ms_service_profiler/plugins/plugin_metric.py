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
        
        metric_cols = [col for col in tx_data_df.columns if is_metric(col)]
        
        metric_data_df = tx_data_df[['start_time'] + metric_cols].copy()
        metric_data_df.loc[tx_data_df['name'] == 'httpReq', 'WAITING+'] = 1.0

        increase_metric_cols = [col for col in metric_cols if col[-1] == "+"]
        metric_data_df[increase_metric_cols] = cal_increase_value(metric_data_df[increase_metric_cols])   

        metric_data_df = metric_data_df.rename(columns={col: col[:-1] for col in metric_cols})
        data['tx_data_df'] = tx_data_df
        data['metric_data_df'] = metric_data_df
        return data


def is_metric(name):
    if isinstance(name, str) and name and name[-1] in ['+', '=']:
        return True
    return False


def cal_increase_value(df):
    df = df.apply(pd.to_numeric, errors='coerce')
    df = df.fillna(0)
    df = df.cumsum(axis=0)
    return df
