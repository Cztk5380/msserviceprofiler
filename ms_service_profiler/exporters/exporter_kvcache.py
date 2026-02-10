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

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import numpy as np

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.constant import US_PER_MS, PERCENTAGE_CONVERSION_FACTOR, PERCENTAGE_THRESHOLD
from ms_service_profiler.exporters.utils import (
    write_result_to_csv, truncate_timestamp, CurveViewConfig,
    write_result_to_db, TableConfig
)


def get_max_free_value(kvcache_df):
    """
    获取所有rid中name为Free的deviceBlock=的最大值
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
            'start_datetime', 'end_datetime'
        ]]
    except KeyError as e:
        logger.warning(f"Field '{e.args[0]}' attr not found in porf data named PullKVCache." \
                       "pd split kvcache data will not be generated. please check")
        return

    # 只处理during_time，移除对start_time和end_time的处理
    pull_kvcache_df['during_time'] = pull_kvcache_df['during_time'] / US_PER_MS

    # 时间格式处理 - 移除毫秒部分
    pull_kvcache_df['start_datetime'] = pull_kvcache_df['start_datetime'].str[:-3]
    pull_kvcache_df['end_datetime'] = pull_kvcache_df['end_datetime'].str[:-3]

    if 'db' in args_format:
        write_result_to_db(CREATE_PULL_KVCACHE_TABLE_CONFIG, pull_kvcache_df)

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
            kvcache_domains = ['KVCache', 'Schedule.KVCache']
            kvcache_mask = df['domain'].isin(kvcache_domains)

            if not kvcache_mask.any():
                logger.warning("No 'KVCache' related fields found in porf data. If this is unexpected, please check")
                return

            try:
                # KVCache事件
                kvcache_df = df[kvcache_mask]

                # 过滤掉CacheHitRate事件，放到request.csv中
                kvcache_df = kvcache_df[kvcache_df['name'] != 'CacheHitRate']
                
                # 检测数据格式类型
                has_old_format = ('deviceBlock=' in kvcache_df.columns and 
                                 kvcache_df['name'].isin(['Allocate', 'AppendSlot']).any())
                
                if has_old_format:
                    # 旧版采集数据处理逻辑
                    selected_columns = [
                        'domain', 'rid', 'start_time', 'name',
                        'deviceBlock=', 'start_datetime'    
                    ]
                    available_columns = [col for col in selected_columns if col in kvcache_df.columns]
                    kvcache_df = kvcache_df[available_columns]
                    
                    # 转换时间单位
                    if 'start_time' in kvcache_df.columns:
                        kvcache_df['start_time'] = kvcache_df['start_time'] // US_PER_MS
                else:
                    # 新版数据格式处理
                    # 选择需要的列 - 包括插件计算出的指标列
                    selected_columns = [
                        'name', 'start_datetime',
                        'total_blocks', 'used_blocks', 'free_blocks',
                        'blocks_allocated', 'blocks_freed', 'kvcache_usage_rate'
                    ]
                    available_columns = [col for col in selected_columns if col in kvcache_df.columns]
                    kvcache_df = kvcache_df[available_columns]

            except KeyError as e:
                logger.warning(f"Field '{e.args[0]}' attribute not found in porf data named KVCache")
                return

        if 'db' in cls.args.format or 'csv' in cls.args.format:
            # 检测数据格式类型
            has_old_format = ('deviceBlock=' in kvcache_df.columns and 
                             kvcache_df['name'].isin(['Allocate', 'AppendSlot']).any())
            
            if has_old_format:
                # 旧版数据格式：需要计算使用率
                kvcache_df = kvcache_usage_rate_calculator(kvcache_df)
            
            if 'db' in cls.args.format:
                # 现在kvcache_df已经包含所有计算好的指标
                kvcache_df['start_datetime'] = truncate_timestamp(kvcache_df['start_datetime'])
                write_result_to_db(CREATE_KVCACHE_TABLE_CONFIG, kvcache_df, CREATE_KVCACHE_VIEW_CONFIG)

            if 'csv' in cls.args.format:
                # 直接使用包含指标的数据
                write_result_to_csv(kvcache_df, output, "kvcache", KVCACHE_RENAME_COLS)

        # PullKVCache
        export_pull_kvcache(df, cls.args.output_path, cls.args.format)


# 更新重命名映射
KVCACHE_RENAME_COLS = {
    'total_blocks': 'total_blocks',
    'used_blocks': 'used_blocks',
    'free_blocks': 'free_blocks',
    'usage_percent': 'usage_percent',
    'blocks_allocated': 'blocks_allocated',
    'blocks_freed': 'blocks_freed',
    'kvcache_usage_rate': 'kvcache_usage_rate',
    'start_datetime': 'start_time'
}

PULL_KV_RENAME_COLS = {
    'during_time': 'during_time(ms)',
    'start_datetime': 'start_time',
    'end_datetime': 'end_time'
}

CREATE_KVCACHE_TABLE_CONFIG = TableConfig(
    table_name="kvcache",
    create_view=True,
    view_name="kvcache_usage",
    view_rename_cols=KVCACHE_RENAME_COLS,
    description={
        "en": "NPU memory usage during servitized inference",
        "zh": "推理过程的显存使用情况"
    }
)

CREATE_PULL_KVCACHE_TABLE_CONFIG = TableConfig(
    table_name="pd_split_kvcache",
    create_view=True,
    view_name="pd_split_pull_kvcache",
    view_rename_cols=PULL_KV_RENAME_COLS,
    description={
        "en": "Metrics of KVCache Transfer Between PD Nodes During PD-Separated Inference",
        "zh": "PD分离推理过程的KVCache在PD节点间的传输情况"
    }
)

KVCACHE_CURVE_VIEW_NAME = "Kvcache_Usage_Percent_curve"
CREATE_KVCACHE_VIEW_SQL = f"""
    CREATE VIEW {KVCACHE_CURVE_VIEW_NAME} AS
    SELECT
        start_datetime AS datetime,
        kvcache_usage_rate * 100 AS kvcache_usage_percent
    FROM
        kvcache
    ORDER BY
        datetime ASC
"""
CREATE_KVCACHE_VIEW_CONFIG = CurveViewConfig(
    view_name=KVCACHE_CURVE_VIEW_NAME,
    sql=CREATE_KVCACHE_VIEW_SQL,
    description={
        "en": "KVCache usage rate for all requests over time",
        "zh": "所有请求Kvcache使用率随时间变换折线图"
    }
)