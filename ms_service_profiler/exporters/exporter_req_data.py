# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import key_except
from ms_service_profiler.exporters.utils import (
    CURVE_VIEW_NAME_LIST, write_result_to_csv,
    write_result_to_db, check_domain_valid
)


def is_invaild_rid(rid):
    return ',' in rid or '{' in rid or ':' in rid


def get_req_base_info(df):
    # 原有分组逻辑
    req_group_df = df.groupby('rid')
    req_base_info = []
    for rid, pre_req_data in req_group_df:
        rid = str(rid)
        if rid == "" or is_invaild_rid(rid):
            continue

        # 构造请求信息
        new_req = {
            'rid': rid,
            'start_time': '',
            'end_time': '',
            'recvTokenSize=': '',
            'replyTokenSize=': '',
            'execution_time': ''
        }

        # 获取httpReq
        http_req_df = pre_req_data[pre_req_data['name'] == 'httpReq']
        if not http_req_df.empty:
            first_row = http_req_df.iloc[0]
            new_req['start_time'] = first_row.get("start_time", 0)

        # 获取 httpRes
        # 由于存在httpRes提前被调用，导致请求结束时间过早的情况，所以当前取httpRes和DecodeEnd中最晚一个点作为请求结束时间
        # mindIE重构后，取最后一个sendResponse的结束时间
        http_res_df = pre_req_data[pre_req_data['name'].isin(['httpRes', 'DecodeEnd', 'sendResponse'])]
        if not http_res_df.empty:
            last_row = http_res_df.iloc[-1]
            new_req['end_time'] = last_row.get("end_time", 0)

        # 获取replyTokenSize
        if 'replyTokenSize=' in pre_req_data.columns and pre_req_data['replyTokenSize='].notna().any():
            # 获取当replyTokenSize列中值不为空时，获取其中的第一个值
            new_req['replyTokenSize='] = pre_req_data['replyTokenSize='].dropna().iloc[0]

        # 获取 recvTokenSize=
        if 'recvTokenSize=' in pre_req_data.columns and pre_req_data['recvTokenSize='].notna().any():
            # 获取当replyTokenSize列中值不为空时，获取其中的第一个值
            new_req['recvTokenSize='] = pre_req_data['recvTokenSize='].dropna().iloc[0]

        # 计算 execution_time
        if new_req['start_time'] != '' and new_req['end_time'] != '':
            new_req['end_time'] = new_req['end_time'] // US_PER_MS
            new_req['start_time'] = new_req['start_time'] // US_PER_MS
            new_req['execution_time'] = (new_req['end_time'] - new_req['start_time'])

        req_base_info.append(new_req)
    return pd.DataFrame(req_base_info)


def safe_merge_ttft_que(req_base_info: pd.DataFrame,
                        ttft_df: pd.DataFrame,
                        que_df: pd.DataFrame) -> pd.DataFrame:
    """
    无 copy 合并 rid、ttft、que_wait_time
    """
    # 1.ttft
    ttft_part = (ttft_df[['rid', 'ttft']]
                 .drop_duplicates('rid') if not ttft_df.empty and 'ttft' in ttft_df.columns
                 else pd.DataFrame(columns=['rid', 'ttft']))

    # 2.que_wait_time
    que_part = (que_df[['rid', 'que_wait_time']]
                .drop_duplicates('rid') if not que_df.empty and 'que_wait_time' in que_df.columns
                else pd.DataFrame(columns=['rid', 'que_wait_time']))

    # 3.合并ttft+que
    metrics = ttft_part.merge(que_part, on='rid', how='outer')

    # 4.与req_base_info合并
    return (
        req_base_info
        .assign(rid=lambda d: d['rid'].astype(str))
        .merge(metrics, on='rid', how='left')
        .assign(
            ttft=lambda d: d['ttft'].fillna(0),
            que_wait_time=lambda d: d['que_wait_time'].fillna(0)
        )
    )


class ExporterReqData(ExporterBase):
    name = "req_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.info)
    @key_except('domain', 'name', ignore=True, msg="ignoring current exporter by default.")
    def export(cls, data) -> None:
        if 'csv' in cls.args.format or 'db' in cls.args.format:
            df = data.get('tx_data_df')
            if df is None:
                logger.error("The data is empty, please check")
                return

            if check_domain_valid(df, ['Request'], 'request') is False:
                return

            output = cls.args.output_path

            df = df[~df['domain'].isin(['KVCache', 'PullKVCache'])]
            df = df[~df['name'].isin(['forward'])]
            ttft_df = data.get("req_ttft_df", pd.DataFrame())  # ttft的单位是微秒，需要转换为毫秒
            ttft_df.loc[:, 'ttft'] = ttft_df['ttft'].div(US_PER_MS)

            que_wait_df = data.get("req_que_wait_df", pd.DataFrame())   # que_wait_df的单位是微秒，需要转换为毫秒
            que_wait_df.loc[:, 'que_wait_time'] = que_wait_df['que_wait_time'].div(US_PER_MS)

            req_base = get_req_base_info(df)
            req_base_info = safe_merge_ttft_que(req_base, ttft_df, que_wait_df)

            filtered_df = req_base_info[[
                'rid', 'start_time', 'recvTokenSize=', 'replyTokenSize=',
                'execution_time', 'que_wait_time', 'ttft'
            ]]

            filtered_df = filtered_df.rename(columns={
                'rid': 'http_rid',
                'recvTokenSize=': 'recv_token_size',
                'replyTokenSize=': 'reply_token_size',
                'ttft': 'first_token_latency',
                'que_wait_time': 'queue_wait_time'
            })

        if 'db' in cls.args.format:
            write_result_to_db(
                df_param_list=[[filtered_df, 'request']],
                table_name='request',
                rename_cols=REQUEST_DATA_RENAME_COLS
            )

        if 'csv' in cls.args.format:
            write_result_to_csv(filtered_df, output, "request", REQUEST_DATA_RENAME_COLS)


REQUEST_DATA_RENAME_COLS = {
    'start_time': 'start_time(ms)', 'execution_time': 'execution_time(ms)',
    'queue_wait_time': 'queue_wait_time(ms)', 'first_token_latency': 'first_token_latency(ms)'
}
