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

from enum import Enum

import pandas as pd

from ms_service_profiler.plugins.base import PluginBase


class ReqStatus(Enum):
    WAITING = 0
    PENDING = 1
    RUNNING = 2
    SWAPPED = 3
    RECOMPUTE = 4
    SUSPENDED = 5
    END = 6
    STOP = 7
    PREFILL_HOLD = 8


class PluginReqStatus(PluginBase):
    name = "plugin_req_status"
    depends = ["plugin_common"]

    @classmethod
    def parse(cls, data):
        tx_data_df = data.get('tx_data_df')
        if tx_data_df is None:
            raise ValueError("tx_data_df is None")
        
        tx_data_df['message'] = tx_data_df['message'].apply(parse_message_state_name)

        req_status_name = [col for col in tx_data_df.columns if is_req_status_metric(col)]
        req_status_name_new = [status_index_to_status_name(metric) for metric in req_status_name]
        tx_data_df = tx_data_df.rename(columns={key: value for key, value in zip(req_status_name, req_status_name_new)})
        data['tx_data_df'] = tx_data_df
        

        data['req_status_df'] = increase_value_to_real_value(tx_data_df, req_status_name_new)
        
        for column in data['req_status_df'].columns:
            if pd.isna(data['req_status_df'][column].iloc[0]): 
                data['req_status_df'][column] = data['req_status_df'][column].fillna(0)        
        subset = data['req_status_df'].iloc[:, 2:]
        condition = subset.isna().all(axis=1)
        data['req_status_df'] = data['req_status_df'][~condition] 
        data['req_status_df'] = data['req_status_df'].infer_objects()
        data['req_status_df'] = data['req_status_df'].ffill()
        
        return data


def increase_value_to_real_value(tx_data_df, req_status_name_new):
    inc_df = tx_data_df[['start_time'] + \
            req_status_name_new].rename(columns={'start_time': 'time/us'})
    df = inc_df.copy()
    df.columns = [col[:-1] if col.endswith('+') or col.endswith('=') else col \
        for col in inc_df.columns]

    cur = [0 for _ in range(len(ReqStatus))]
    for i, _ in inc_df.iterrows():
        name = tx_data_df['name'].iloc[i]
        if name == "httpReq":
            cur[0] += 1
            df.iloc[i, 1] = cur[0]
        elif name == "ReqState":
            count_req_state(inc_df, df, cur, i)
    return df


def count_req_state(inc_df, df, cur, index):
    for j, _ in enumerate(inc_df.columns[1:]):
        inc_value = inc_df.iloc[index, 1+j]
        if inc_value is None:
            continue
        cur[j] += inc_value
        df.iloc[index, 1+j] = cur[j]


def is_metric(name):
    if name[-1] in ['+', '=']:
        return True
    return False


def is_req_status_metric(metric):
    # 验证 metric 的格式
    flag = is_metric(metric) and metric[:-1].isdigit()
    return flag


def status_index_to_status_name(metric):
    # 验证 metric 的格式
    if not is_metric(metric) or not metric[:-1].isdigit():
        return metric
    
    try:
        index = int(metric[:-1])
    except ValueError as ex:
        raise ValueError(f"Invalid status index: {metric[:-1]}") from ex
    
    # 确保索引在 ReqStatus 的范围内
    if index not in [status.value for status in ReqStatus]:
        raise ValueError(f"Invalid status index: {index}")
    
    return f"{ReqStatus(index).name}{metric[-1]}"


def parse_message_state_name(message):
    if not isinstance(message, dict):
        raise ValueError(f"Message must be a dict, but got {type(message)}")
    
    new_message = {}
    for key, value in message.items():
        new_message[status_index_to_status_name(key)] = value
    return new_message
