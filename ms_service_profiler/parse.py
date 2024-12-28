# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
from pathlib import Path
import json
import re
import sqlite3
from pathlib import Path
from collections import defaultdict

import pandas as pd

from ms_service_profiler.constant import US_PER_SECOND
from ms_service_profiler.plugins import buildin_plugins
from ms_service_profiler.plugins.sort_plugins import sort_plugins
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import ParseError, ExportError, LoadDataError


def save_dataframe_to_csv(filtered_df, output, file_name):
    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = output_path / file_name
        filtered_df.to_csv(file_path, index=False)


def load_start_cnt(config_path):
    sys_start_cnt = 0
    cpu_start_cnt = 0
    with open(config_path, 'r') as f:
        for line in f:
            if "cntvct:" in line:
                sys_start_cnt = int(line.strip().split(": ")[1])
            elif "clock_monotonic_raw:" in line:
                cpu_start_cnt = int(line.strip().split(": ")[1])
    if sys_start_cnt == 0 or cpu_start_cnt == 0:
        raise ValueError(f"Failed to find 'cntvct' or 'clock_monotonic_raw' in {config_path}, please check.")
    return sys_start_cnt, cpu_start_cnt


def load_start_time(start_info_path):
    file_description = os.open(start_info_path, os.O_RDONLY)
    with os.fdopen(file_description, 'r') as info:
        data = json.load(info)
        if 'collectionTimeBegin' not in data:
            raise ValueError(f"Invalid or missing 'CPU' data in {start_info_path}.")
        sys_start_time = float(data['collectionTimeBegin']) / 1e6
    return sys_start_time


def load_tx_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM MsprofTxEx
    """)

    all_data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    all_data_df = pd.DataFrame(all_data, columns=columns)
    all_data_df = parse_span(all_data_df)
    conn.close()
    return all_data_df


def extract_span_info_from_message(message, mark_id):
    span_id = str(mark_id)
    groups = re.match("span=(\\d+)[|*](.*)", message)
    if groups:
        span_id = groups[1]
        message = groups[2]
    return span_id, message


def load_cpu_data(db_path):
    if db_path is None:
        return None
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


def load_cpu_freq(info_path):
    cpu_frequency = None
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


def get_filepaths(folder_path, file_filter):
    filepaths = {}
    reverse_d = {value: key for key, value in file_filter.items()}
    for fp in Path(folder_path).rglob('*'):
        if fp.name in reverse_d:
            filepaths[reverse_d[fp.name]] = str(fp)
    return filepaths


def merge_message(series):
    series_merge = series.sort_values("mark_id")
    all_msg = "".join(series_merge["message"]).replace("^", "\"")
    series_merge.iloc[0, series_merge.columns.get_loc("message")] = all_msg
    return series_merge.iloc[0]


def parse_span(data_df):
    span_info = data_df[["mark_id", "message"]].apply(
        lambda x: extract_span_info_from_message(x["message"], x["mark_id"]), axis=1
    )
    data_df[["span_id", "message"]] = pd.DataFrame(span_info.tolist())
    data_df = data_df.groupby("span_id").apply(merge_message, include_groups=False)
    return data_df


def load_time_info(filepaths):
    sys_start_cnt, cpu_start_cnt = load_start_cnt(filepaths.get("host_start"))
    cpu_frequency = load_cpu_freq(filepaths.get("info"))
    sys_start_time = load_start_time(filepaths.get("start_info"))
    return dict(
        sys_start_cnt=sys_start_cnt,
        cpu_start_cnt=cpu_start_cnt,
        sys_start_time=sys_start_time,
        cpu_frequency=cpu_frequency
    )


def load_prof(filepaths):
    tx_data_df = load_tx_data(filepaths.get("tx"))
    cpu_data_df = load_cpu_data(filepaths.get("cpu"))
    time_info = load_time_info(filepaths)

    return dict(
        tx_data_df=tx_data_df,
        cpu_data_df=cpu_data_df,
        time_info=time_info,
    )


def read_origin_db(db_path: str):
    file_filter = {
        "tx": "msproftx.db",
        "cpu": "host_cpu_usage.db",
        "host_start": "host_start.log",
        "info": "info.json",
        "start_info": "start_info",
    }

    data_list = []

    for dp in Path(db_path).glob("**/PROF_*"):
        filepaths = get_filepaths(dp, file_filter)
        try:
            data = load_prof(filepaths)
            data_list.append(data)
        except Exception as ex:
            raise LoadDataError(str(dp)) from ex
    return data_list


def parse(input_path, custom_plugins, exporters):
    logger.info('Start to parse.')
    # 解析数据
    data = read_origin_db(input_path)
    logger.info('Read origin db success.')

    all_plugins = sort_plugins(buildin_plugins + custom_plugins)
    for plugin in all_plugins:
        try:
            data = plugin.parse(data)
            logger.info(f'{plugin.name} success.')
        except ParseError as ex:
            if plugin.name in ['plugin_timestamp', 'plugin_concat']:
                logger.exception(f'{plugin.name} failure. Program stopped.')
                return
            else:
                logger.exception(f'{plugin.name} failure. Skip it.')
    
    # 导出数据
    for exporter in exporters:
        try:
            exporter.export(data)
            logger.info(f'exporter {exporter.name} success.')
        except ExportError as ex:
            logger.exception(f'exporter {exporter.name} failure. Skip it.')
