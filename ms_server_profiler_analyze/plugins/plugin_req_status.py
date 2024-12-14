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

from ms_server_profiler.plugins.base import PluginBase


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

        new_columns = [status_index_to_status_name(metric) for metric in tx_data_df.columns]
        tx_data_df.columns = new_columns
        data['tx_data_df'] = tx_data_df
        return data


def is_metric(name):
    if name[0] in ['+', '=']:
        return True
    return False


def status_index_to_status_name(metric):
    # 验证 metric 的格式
    if not is_metric(metric) or not metric[1:].isdigit():
        return metric
    
    try:
        index = int(metric[1:])
    except ValueError as ex:
        raise ValueError(f"Invalid status index: {metric[1:]}") from ex
    
    # 确保索引在 ReqStatus 的范围内
    if index not in [status.value for status in ReqStatus]:
        raise ValueError(f"Invalid status index: {index}")
    
    return f"{metric[0]}{ReqStatus(index).name}"


def parse_message_state_name(message):
    if not isinstance(message, dict):
        raise ValueError(f"Message must be a dict, but got {type(message)}")
    
    new_message = {}
    for key, value in message.items():
        new_message[status_index_to_status_name(key)] = value
    return new_message
