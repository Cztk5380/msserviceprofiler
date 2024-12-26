# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from enum import Enum
from pathlib import Path
import argparse
import os
import sqlite3
import json
import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.parse import save_dataframe_to_csv


def get_max_free_value(kvcache_df):
    """
    获取所有rid中name为Free的device_kvcache_left的最大值
    """
    all_free_values = kvcache_df[kvcache_df['name'] == 'Free']['device_kvcache_left'].values
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
            timestamp = row['real_start_time']
            action_usage_rate_dict = {}
            action_usage_rate_dict['original_index'] = index
            value = row['device_kvcache_left']
            usage_rate = calculate_action_usage_rate(action, value, max_free_value)
            if usage_rate is not None:
                action_usage_rate_dict['usage'] = usage_rate
            action_usage_rate_dict['timestamp'] = timestamp
            action_usage_rates_list.append(action_usage_rate_dict)
        rid_to_action_usage_rates[rid] = action_usage_rates_list
    return rid_to_action_usage_rates


def build_result_df(kvcache_df, rid_to_action_usage_rates):
    """
    创建新的DataFrame并填充数据
    """
    new_columns = ['rid', 'name', 'real_start_time', 'device_kvcache_left', 'kvcache_usage_rate']
    result_df = pd.DataFrame(columns=new_columns)
    for index, row in kvcache_df.iterrows():
        rid = row['rid']
        action = row['name']
        timestamp = row['real_start_time']
        device_kvcache_left = row['device_kvcache_left']
        if rid in rid_to_action_usage_rates:
            relevant_data_list = [d for d in rid_to_action_usage_rates[rid] if d['original_index'] == index]
            if relevant_data_list:
                usage_rate = relevant_data_list[0]['usage'] if relevant_data_list[0]['usage'] is not None else None
            else:
                usage_rate = None
        else:
            usage_rate = None
        new_row = pd.Series({
            'rid': rid,
            'name': action,
            'real_start_time': timestamp,
            'device_kvcache_left': device_kvcache_left,
            'kvcache_usage_rate': usage_rate
        })
        result_df = pd.concat([result_df, new_row.to_frame().T], ignore_index=True)
    return result_df


def kvcache_usage_rate_calculator(kvcache_df):
    """
    根据不同的action计算kvcache_usage_rate列的值，并添加到传入的DataFrame中
    """
    max_free_value = get_max_free_value(kvcache_df)
    rid_to_action_usage_rates = build_rid_to_action_usage_rates(kvcache_df, max_free_value)
    result_df = build_result_df(kvcache_df, rid_to_action_usage_rates)
    return result_df


def save_csv_to_sqlite(df, input_path):
    db_path = input_path
    conn = sqlite3.connect(db_path)
    df.to_sql('kvcache', conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()


def create_sqlite_db(output):
    if not os.path.exists(output):
        os.makedirs(output)
    db_file = os.path.join(output, '.profiler.db')
    conn = sqlite3.connect(db_file)
    conn.isolation_level = None
    cursor = conn.cursor()
    conn.close()
    return db_file


class ExporterKVCacheData(ExporterBase):
    name = "kvcache_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')
        if df is None:
            logging.error("The data is empty, please check")
            return
        start_datatime_data = df['start_datatime'].copy()
        try:
            kvcache_df = df[df['domain'] == 'KVCache']
            kvcache_df = kvcache_df[['domain', 'rid', 'start_time', 'end_time', 'name', \
                                     'deviceBlock=', 'during_time']]
            kvcache_df = kvcache_df.rename(columns={
                'deviceBlock=': 'device_kvcache_left',
                'start_time': 'start_time(microsecond)',
                'end_time': 'end_time(microsecond)',
                'during_time': 'during_time(microsecond)'
            })
        except KeyError as e:
            logger.warning(f"Field '{e.args[0]}' not found in msproftx.db.")
        kvcache_df = df[df['domain'] == 'KVCache']
        kvcache_df = kvcache_df.rename(columns={'deviceBlock=': 'deviceKvCache'})
        kvcache_df = kvcache_df[['domain', 'rid', 'start_time', 'end_time', 'name', \
            'deviceKvCache', 'during_time']]
        kvcache_df = kvcache_df.rename(columns={
            'deviceKvCache': 'device_kvcache_left',
            'start_time': 'start_time(microsecond)',
            'end_time': 'end_time(microsecond)',
            'during_time': 'during_time(microsecond)'
        })
        output = cls.args.output_path
        save_dataframe_to_csv(kvcache_df, output, "kvcache.csv")
        kvcache_df['start_datatime'] = start_datatime_data
        kvcache_df = kvcache_df.rename(columns={
        'start_datatime': 'real_start_time'
        })
        kvcache_df = kvcache_usage_rate_calculator(kvcache_df)
        db_file_path = create_sqlite_db(output)
        save_csv_to_sqlite(kvcache_df, db_file_path)