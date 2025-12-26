# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

from enum import Enum

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.plugins.plugin_metric import is_metric
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer


class ReqStatus(Enum):
    WAITING = 0       # Waiting to Prefill
    PENDING = 1       # Waiting to Decode  KV Cache not swapped  Associated with Instance
    RUNNING = 2       # Executing Prefill or Decode  Associated with Instance
    RUNNING2 = 3      # Executing Prefill or Decode  Associated with Instance  using in async schedule
    SWAPPED = 4       # Waiting to Decode  KV Cache swapped
    RECOMPUTE = 5     # KV cache is released and will later be WAITING
    SUSPENDED = 6     # Waiting for the next INFER control calling to make it resume
    END = 7           # Execute end
    STOP = 8          # User Control State  Stop Sequence iteration
    PREFILL_HOLD = 9  # Waiting for the decode to pull cache
    END_PRE = 10      # Execute end using in async schedule
    STOP_PRE = 11     # Waiting for RUNNING2 request back in async schedule
    WAITING_PULL = 12 # Decode do H2H pull
    PULLING = 13      # Executing H2H pull
    PULLED = 14       # H2H pull is done and ready for H2D
    D2D_PULLING = 15  # Decode doing D2D pulling


class PluginReqStatus(PluginBase):
    name = "plugin_req_status"
    depends = ["plugin_common"]
    _warned_no_request_status = False

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        tx_data_df = data.get('tx_data_df')
        if tx_data_df is None or tx_data_df.empty:
            return data

        # mindIE 重构后，不再使用数字映射状态码的方式，直接从status列中可取得状态，如waiting、running、swapped
        if 'status' in tx_data_df.columns:
            return data

        tx_data_df['message'] = tx_data_df['message'].apply(parse_message_state_name)
        rename_mapping = {
            col: status_index_to_status_name(col)
            for col in tx_data_df.columns
            if is_req_status_metric(col)
        }
        tx_data_df = tx_data_df.rename(columns=rename_mapping)
        req_status = list(rename_mapping.values())
        if req_status:
            tx_data_df = rename_req_status(tx_data_df, req_status)
        else:
            vllm_req_status = ['WAITING+', 'RUNNING+', 'FINISHED+']
            # 筛选出tx_data_df中真实存在的列
            valid_cols = [col for col in vllm_req_status if col in tx_data_df.columns]

            if not valid_cols and not cls._warned_no_request_status:
                logger.warning(
                    "No 'request status' is found in prof data, if this is unexpected, please check"
                )
                cls._warned_no_request_status = True
                return data

            tx_data_df = rename_req_status(tx_data_df, valid_cols)

        # 填充domain和name
        if 'domain' in tx_data_df.columns:
            tx_data_df['name'] = tx_data_df['name'].fillna(tx_data_df['domain'])
            tx_data_df['domain'] = tx_data_df['domain'].fillna(tx_data_df['name'])

        data['tx_data_df'] = tx_data_df
        return data


def is_req_status_metric(metric):
    # 验证 metric 的格式
    flag = is_metric(metric) and metric[:-1].isdigit()
    return flag


def status_index_to_status_name(metric):
    # 验证 metric 的格式
    if not is_req_status_metric(metric):
        return metric

    try:
        index = int(metric[:-1])
    except ValueError as ex:
        raise ValueError(f"Invalid status index: {metric[:-1]}") from ex

    # 确保索引在 ReqStatus 的范围内
    if index not in [status.value for status in ReqStatus]:
        return metric

    return f"{ReqStatus(index).name}{metric[-1]}"


def parse_message_state_name(message):
    if not isinstance(message, dict):
        raise ValueError(f"Message must be a dict, but got {type(message)}")

    new_message = {}
    for key, value in message.items():
        new_message[status_index_to_status_name(key)] = value
    return new_message


def rename_req_status(tx_data_df, req_status):
    real_status = tx_data_df[req_status].gt(0)
    real_status.columns = real_status.columns.str.replace('+', '', regex=False)

    # 当前修改只针对name为ReqState的行生效；创建一个行索引，选择满足条件的行
    indexer = tx_data_df['name'] == 'ReqState'
    # 使用这个索引来更新'name'列
    tx_data_df.loc[indexer, 'name'] = real_status.idxmax(axis=1).where(real_status.any(axis=1), \
        tx_data_df.loc[indexer, 'name'])

    #将所有原始name为'ReqState'的行的domain列设置为"RequestState"，以便在trace图中作为一个单独的泳道
    tx_data_df.loc[indexer, 'domain'] = "RequestState"
    return tx_data_df
