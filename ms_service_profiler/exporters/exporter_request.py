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
import logging
from pathlib import Path
import json
import pandas as pd


from ms_service_profiler.parse import parse
from ms_service_profiler.parse import save_dataframe_to_csv
from ms_service_profiler.exporters.base import ExporterBase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def update_name(row):
    if row['RUNNING+'] == 1:
        row['name'] = 'RUNNING'
    elif row['PENDING+'] == 1:
        row['name'] = 'PENDING'
    return row


def process_data(req_en_queue_df, req_running_df, pending_df):
    """
    处理数据，计算等待时间和执行时间。

    参数:
    req_en_queue_df (pd.DataFrame): 请求队列的数据
    req_running_df (pd.DataFrame): 正在运行的请求的数据
    pending_df (pd.DataFrame): 等待中的请求的数据

    返回:
    wait_df (pd.DataFrame): 包含等待时间和执行时间的DataFrame
    """
    # 分组并取第一个
    decode_first_df = req_en_queue_df.groupby('rid').head(1)
    running_first_df = req_running_df.groupby('rid').head(1)

    if decode_first_df.shape[0] == running_first_df.shape[0]:
        prefill_df = pd.merge(decode_first_df, running_first_df, on=['rid'], suffixes=('_enque', '_running'))
    else:
        logging.error("The data is wrong, please check")
        return None
    prefill_df['waiting_time'] = prefill_df["start_time_running"] - prefill_df["end_time_enque"]
    decode_running_df = req_running_df.groupby('rid').apply(lambda x: x.iloc[1:]).reset_index(drop=True)
    pending_df = pending_df.reset_index(drop=True)
    pending_df = pending_df[['start_time', 'end_time', 'rid']]
    decode_running_df = decode_running_df[['start_time', 'end_time', 'rid']]
    rows_pending = pending_df.shape[0]
    rows_running = decode_running_df.shape[0]
    if rows_pending == rows_running:
        decode_merge = pd.concat([pending_df, decode_running_df], ignore_index=True, axis=1)
    else:
        logging.error("The data is wrong, please check")
        return None
    decode_merge.columns = ['start_time_pending', 'end_time_pending', 'rid', 'start_time_running', \
        'end_time_running', 'rid_running']
    decode_merge["pending_time"] = decode_merge['start_time_running'] - decode_merge['start_time_pending']
    decode_merge = decode_merge.drop(columns=['start_time_running', 'end_time_running'])
    pending_time_sum = decode_merge.groupby('rid')['pending_time'].sum().reset_index()
    if prefill_df.shape[0] == pending_time_sum.shape[0]:
        wait_df = pd.merge(prefill_df, pending_time_sum, on='rid')
    else:
        logging.error("The data is wrong, please check")
        return None
    wait_df['queue_wait_time'] = wait_df['waiting_time'] + wait_df['pending_time']
    wait_df['rid'] = pd.to_numeric(wait_df['rid'], errors='coerce')
    wait_df = wait_df[['rid', 'queue_wait_time']]
    return wait_df


class ExporterAnalyzeData(ExporterBase):
    name = "request_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')
        if df is None:
            logging.error("The data is empty, please check")
            return
        output = cls.args.output_path
        df = df.apply(update_name, axis=1)
        http_req_df = df[df['name'] == 'httpReq'].drop(columns=['name'])
        http_res_df = df[df['name'] == 'httpRes'].drop(columns=['name'])
        http_rectoken_df = df[df['name'] == 'encode'].drop(columns=['name'])
        http_restoken_df = df[df['name'] == 'DecodeEnd'].drop(columns=['name'])
        req_en_queue_df = df[df['name'] == 'ReqEnQueue'].drop(columns=['name'])
        req_running_df = df[df['name'] == 'RUNNING']
        pending_df = df[df['name'] == 'PENDING'].drop(columns=['name'])
        wait_df = process_data(req_en_queue_df, req_running_df, pending_df)
        # 使用merge操作将httpReq和httpRes的数据进行匹配
        if http_req_df.shape[0] == http_res_df.shape[0]:
            df_merged = pd.merge(http_req_df, http_res_df, on='rid', suffixes=('_httpReq', '_httpRes'))
        else:
            logging.error("The data is wrong, please check")
            return
        # 计算execution_time
        if df_merged.shape[0] == wait_df.shape[0]:
            df_merged['rid'] = pd.to_numeric(df_merged['rid'], errors='coerce')
            df_merged = pd.merge(df_merged, wait_df, on='rid')
        else:
            logging.error("The data is wrong, please check")
            return
        http_rectoken_df = http_rectoken_df[['rid', 'recvTokenSize=']]
        http_restoken_df = http_restoken_df[['rid', 'replyTokenSize=']]
        if http_rectoken_df.shape[0] == http_restoken_df.shape[0]:
            df_token = pd.merge(http_rectoken_df, http_restoken_df, on='rid')
        else:
            logging.error("The data is wrong, please check")
            return
        if df_merged.shape[0] == df_token.shape[0]:
            df_token['rid'] = pd.to_numeric(df_token['rid'], errors='coerce')
            df_merged = pd.merge(df_merged, df_token, on='rid')
        else:
            logging.error("The data is wrong, please check")
            return
        
        df_merged['execution_time'] = df_merged['end_time_httpRes'] - df_merged['start_time_httpReq']
        df_merged['http_rid'] = df_merged['message_httpReq'].apply(lambda x: x['rid'])
        filtered_df = df_merged[['http_rid', 'start_time_httpReq', 'recvTokenSize=', 'replyTokenSize=', \
            'execution_time', 'queue_wait_time']]
        filtered_df = filtered_df.rename(columns={
            'recvTokenSize=': 'recv_token_size',
            'replyTokenSize=': 'reply_token_size',
            'start_time_httpReq': 'start_time_httpReq(microsecond)',
            'execution_time': 'execution_time(microsecond)',
            'queue_wait_time': 'queue_wait_time(microsecond)'
        })
        
        save_dataframe_to_csv(filtered_df, output, "request.csv")


