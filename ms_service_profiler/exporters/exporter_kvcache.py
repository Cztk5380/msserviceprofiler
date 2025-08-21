# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import numpy as np

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.exporters.utils import (
    write_result_to_csv, truncate_timestamp_np,
    check_domain_valid, write_result_to_db, CURVE_VIEW_NAME_LIST
)


def get_max_free_value(kvcache_df):
    """
    获取所有rid中name为Free的device_kvcache_left的最大值
    """
    all_free_values = kvcache_df[kvcache_df['name'] == 'Free']['deviceBlock='].values
    return all_free_values.max() if len(all_free_values) > 0 else 0


def calculate_action_usage_rate(action, value, max_free_value):
    """
    根据不同的action和对应的值以及最大可用值来计算使用率
    """
    if action in ['Allocate', 'AppendSlot', 'Free']:
        if max_free_value > 0:
            return (max_free_value - value) / max_free_value
        return 0
    return 0


def build_rid_to_action_usage_rates(kvcache_df, max_free_value):
    """
    按照rid进行分组，构建每个rid下不同action对应的使用率数据结构
    """
    grouped = kvcache_df.groupby('rid')
    rid_to_action_usage_rates = {}
    for rid, group in grouped:
        action_usage_rates_list = []
        for index, row in group.iterrows():
            action = row['name']
            timestamp = row['start_datetime']
            action_usage_rate_dict = {}
            action_usage_rate_dict['original_index'] = index
            value = row['deviceBlock=']
            usage_rate = calculate_action_usage_rate(action, value, max_free_value)
            if usage_rate is not None:
                action_usage_rate_dict['usage'] = usage_rate
            action_usage_rate_dict['timestamp'] = timestamp
            action_usage_rates_list.append(action_usage_rate_dict)
        rid_to_action_usage_rates[rid] = action_usage_rates_list
    return rid_to_action_usage_rates


def build_result_df(kvcache_df, rid_to_action_usage_rates, num_threads=4):
    """
    创建新的DataFrame并填充数据
    """
    new_columns = ['rid', 'name', 'start_datetime', 'device_kvcache_left', 'kvcache_usage_rate']

    # 将 DataFrame 转换为 NumPy 数组，并添加原始索引作为最后一列
    data_with_index = np.column_stack((kvcache_df.to_numpy(), kvcache_df.index))

    # 处理单行数据的函数
    def process_row(row):
        rid = row[1]
        original_index = row[6]

        relevant_data_list = rid_to_action_usage_rates.get(rid, [])
        relevant_data = next((d for d in relevant_data_list if d['original_index'] == original_index), None)
        usage_rate = relevant_data['usage'] if relevant_data and relevant_data['usage'] is not None else None
        result = [rid, row[3], row[5], row[4], usage_rate]

        return result

    # 分块处理函数
    def process_chunk(chunk):
        return [process_row(row) for row in chunk]

    # 分块大小 num_threads默认为4
    num_threads = max(1, num_threads)
    chunk_size = max(1, len(data_with_index) // num_threads)
    chunks = [
        data_with_index[i:i + chunk_size]
        for i in range(0, len(data_with_index), chunk_size)
    ]

    # 使用线程池并行处理
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(process_chunk, chunks))

    # 合并结果
    data = [
        item
        for sublist in results
        for item in sublist
    ]

    # 创建新的 DataFrame
    result_df = pd.DataFrame(data, columns=new_columns)
    return result_df


def kvcache_usage_rate_calculator(kvcache_df):
    """
    根据不同的action计算kvcache_usage_rate列的值，并添加到传入的DataFrame中
    """
    max_free_value = get_max_free_value(kvcache_df)
    rid_to_action_usage_rates = build_rid_to_action_usage_rates(kvcache_df, max_free_value)
    result_df = build_result_df(kvcache_df, rid_to_action_usage_rates)
    return result_df


def export_pull_kvcache(df, output, args_format):
    pull_kvcache_df = df[df['name'] == 'PullKVCache']
    logger.debug(f"pd_split_kvcache shape {pull_kvcache_df.shape}.")

    if pull_kvcache_df.shape[0] == 0:
        return
    try:
        pull_kvcache_df = pull_kvcache_df[[
            'domain', 'rank', 'rid', 'block_tables', 'batch_seq_len', 'during_time', \
            'start_datetime', 'end_datetime', 'start_time', 'end_time',
        ]]
    except KeyError as e:
        logger.warning(f"Field '{e.args[0]}' attr not found in porf data named PullKVCache." \
            "pd split kvcache data will not be generated. please check")

    pull_kvcache_df['start_time'] = pull_kvcache_df['start_time'] // US_PER_MS
    pull_kvcache_df['end_time'] = pull_kvcache_df['end_time'] // US_PER_MS
    pull_kvcache_df['during_time'] = pull_kvcache_df['during_time'] / US_PER_MS
    
    pull_kvcache_df['start_datetime'] = pull_kvcache_df['start_datetime'].str[:-3]
    pull_kvcache_df['end_datetime'] = pull_kvcache_df['end_datetime'].str[:-3]

    if 'db' in args_format:
        write_result_to_db(
            df_param_list=[[pull_kvcache_df, 'pd_split_kvcache']],
            table_name='pd_split_kvcache',
            rename_cols=PULL_KV_RENAME_COLS
        )

    if 'csv' in args_format:
        write_result_to_csv(pull_kvcache_df, output, 'pd_split_kvcache', PULL_KV_RENAME_COLS)


class ExporterKVCacheData(ExporterBase):
    name = "kvcache_data"
 
    @classmethod
    def initialize(cls, args):
        cls.args = args
 
    @classmethod
    @timer(logger.debug)
    def export(cls, data) -> None:
        df = data.get('tx_data_df')
        if df is None:
            logger.error("cannot find service prof data, please check")
            return
        output = cls.args.output_path

        if 'db' in cls.args.format or 'csv' in cls.args.format:
            if check_domain_valid(df, ['KVCache'], 'kvcache') is False:
                return

            if not df['domain'].str.casefold().str.contains(r'kvcache', regex=True).any():
                logger.warning("No 'KVCache' related fields found in porf data. If this is unexpected, please check")
                return

            try:
                # KVCache事件
                kvcache_df = df[df['domain'] == 'KVCache']
                kvcache_df = kvcache_df[['domain', 'rid', 'start_time', 'name', \
                                        'deviceBlock=', 'start_datetime']]
                kvcache_df['start_time'] = kvcache_df['start_time'] // US_PER_MS
            except KeyError as e:
                logger.warning(f"Field '{e.args[0]}' attribute not found in porf data named KVCache")
        

        if 'db' in cls.args.format:
            kvcache_usuage_df = kvcache_usage_rate_calculator(kvcache_df)
            kvcache_usuage_df['start_datetime'] = truncate_timestamp_np(kvcache_usuage_df['start_datetime'])
            write_result_to_db(
                df_param_list=[[kvcache_usuage_df, 'kvcache']],
                table_name='kvcache',
                create_view_sql=[CREATE_KVCACHE_VIEW_SQL],
                rename_cols=KVCACHE_RENAME_COLS
            )

        if 'csv' in cls.args.format:
            kvcache_df = kvcache_df.drop(['start_datetime'], axis=1)
            write_result_to_csv(kvcache_df, output, "kvcache", KVCACHE_RENAME_COLS)

        # PullKVCache
        export_pull_kvcache(df, cls.args.output_path, cls.args.format)


CREATE_KVCACHE_VIEW_SQL = f"""
    CREATE VIEW {CURVE_VIEW_NAME_LIST['kvcache']} AS
    WITH converted AS (
        SELECT
            kvcache_usage_rate * 100 AS kvcache_usage_percent,
            substr("start_datetime", 1, 10) || ' ' || substr("start_datetime", 12, 8) AS datetime
        FROM
            kvcache
    )
    SELECT
        datetime as time,
        cast(kvcache_usage_percent as REAL) as "kvcacge_usage"
    FROM
        converted
    ORDER BY
        datetime ASC
"""

KVCACHE_RENAME_COLS = {
    'deviceBlock=': 'device_kvcache_left', 'start_time': 'timestamp(ms)',
    'start_datetime': 'start_datetime(ms)'
}

PULL_KV_RENAME_COLS = {
    'start_time': 'start_time(ms)', 'end_time': 'end_time(ms)', 'during_time': 'during_time(ms)',
    'start_datetime': 'start_datetime(ms)', 'end_datetime': 'end_datetime(ms)'
}