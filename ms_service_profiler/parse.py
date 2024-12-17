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

import os
import json
import sqlite3
from sqlite3 import Error
import pandas as pd

from ms_service_profiler.constant import US_PER_SECOND
from ms_service_profiler.plugins import buildin_plugins
from ms_service_profiler.plugins.sort_plugins import sort_plugins


def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f"Connected to {db_file}")
    except Error as e:
        print(f"Error: {e}")
    return conn


def df_to_sqlite(df, db_file, table_name):
    conn = create_connection(db_file)
    if conn:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()
        print(f"Data has been written to {db_file}")


def find_config_files(folder_path):
    config_path = None
    info_path = None
    for root, _, files in os.walk(folder_path):
        for filename in files:
            if filename == 'host_start.log':
                config_path = os.path.join(root, filename)
            if filename == 'info.json':
                info_path = os.path.join(root, filename)
    if config_path is None or info_path is None:
        raise ValueError(f"Failed to get 'host_start.log' or 'info.json' from {folder_path}, please check.")
    return config_path, info_path


def get_start_cnt(folder_path):
    sys_start_cnt = 0
    cpu_start_cnt = 0
    config_path, _ = find_config_files(folder_path)
    with open(config_path, 'r') as f:
        for line in f:
            if "cntvct:" in line:
                sys_start_cnt = int(line.strip().split(": ")[1])
            elif "clock_monotonic_raw:" in line:
                cpu_start_cnt = int(line.strip().split(": ")[1])
    if sys_start_cnt == 0 or cpu_start_cnt == 0:
        raise ValueError(f"Failed to find 'cntvct' or 'clock_monotonic_raw' in {config_path}, please check.")
    return sys_start_cnt, cpu_start_cnt


def load_data_from_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM MsprofTxEx
    """)

    all_data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    all_data_df = pd.DataFrame(all_data, columns=columns)
    conn.close()
    return all_data_df


def extract_span_info_from_message(message, mark_id):
    span_id = str(mark_id)
    if message.startswith('span') and '|' in message and '=' in message:
        span_part = message.split("|")[0]
        span_id = span_part.split("=")[1]
        message = message.split("|")[1]
        return span_id, message
    return span_id, message


def concat_data_from_folder(folder_path):
    full_df = pd.DataFrame()
    
    def merge_message(series):
        series_merge = series.sort_values("mark_id")
        series_merge.iloc[0, series_merge.columns.get_loc("message")] = "".join(series_merge["message"])
        return series_merge.iloc[0]
    
    for root, _, files in os.walk(folder_path):
        for filename in files:
            if filename == 'msproftx.db':
                db_path = os.path.join(root, filename)
                data_df = load_data_from_database(db_path)
                
                span_info = data_df[["mark_id", "message"]].apply(
                    lambda x: extract_span_info_from_message(x["message"], x["mark_id"]), axis=1
                )
                data_df[["span_id", "message"]] = pd.DataFrame(span_info.tolist())
                data_df = data_df.groupby("span_id").apply(merge_message, include_groups=False)
                
                full_df = pd.concat([full_df, data_df], ignore_index=True)
    if full_df.empty:
        raise ValueError(f"No valid database found in {folder_path}, please check.")
    full_df = full_df.sort_values(by='start_time', ascending=True).reset_index(drop=True)
    return full_df


def load_cpu_data_from_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM CpuUsage
        WHERE cpu_no == 'Avg'
    """)

    cpu_data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    cpu_data_df = pd.DataFrame(cpu_data, columns=columns)
    conn.close()
    return cpu_data_df


def find_cpu_data_from_folder(folder_path):
    cpu_data_df = pd.DataFrame()
    for root, _, files in os.walk(folder_path):
        for filename in files:
            if filename == 'host_cpu_usage.db':
                db_path = os.path.join(root, filename)
                cpu_data_df = load_cpu_data_from_database(db_path)
    if cpu_data_df.empty:
        raise ValueError(f"No valid cpu database found in {folder_path}, please check.")
    cpu_data_df = cpu_data_df.sort_values(by='start_time', ascending=True).reset_index(drop=True)
    return cpu_data_df


def get_cpu_freq(folder_path):
    cpu_frequency = None
    _, info_path = find_config_files(folder_path)
    file_description = os.open(info_path, os.O_RDONLY)
    with os.fdopen(file_description, 'r') as info:
        data = json.load(info)
        if 'CPU' not in data or not isinstance(data['CPU'], list) or len(data['CPU']) == 0:
            raise ValueError(f"Invalid or missing 'CPU' data in {info_path}.")
        cpu_data = data['CPU'][0]
        cpu_frequency = cpu_data.get('Frequency', None)
        if cpu_frequency is None:
            raise KeyError(f"Missing 'Frequency' value in 'CPU' data.")
        cpu_frequency = float(cpu_frequency) * US_PER_SECOND
    return cpu_frequency


def read_origin_db(db_path: str):    
    tx_data_df = concat_data_from_folder(db_path)
    cpu_data_df = find_cpu_data_from_folder(db_path)
    sys_start_cnt, cpu_start_cnt = get_start_cnt(db_path)
    cpu_frequency = get_cpu_freq(db_path)

    return dict(
        tx_data_df=tx_data_df,
        cpu_data_df=cpu_data_df,
        sys_start_cnt=sys_start_cnt,
        cpu_start_cnt=cpu_start_cnt,
        cpu_frequency=cpu_frequency
        )


def parse(input_path, custom_plugins, exporters):
    # 解析数据
    data = read_origin_db(input_path)

    all_plugins = sort_plugins(buildin_plugins + custom_plugins)
    for plugin in all_plugins:
        data = plugin.parse(data)

    # 导出数据
    for exporter in exporters:
        exporter.export(data)

