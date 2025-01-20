# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
from pathlib import Path
import json
import re
import sqlite3
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from ms_service_profiler.constant import US_PER_SECOND
from ms_service_profiler.plugins import builtin_plugins
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
    cntvct = 0
    clock_monotonic_raw = 0
    with open(config_path, 'r') as f:
        for line in f:
            if "cntvct:" in line:
                cntvct = int(line.strip().split(": ")[1])
            elif "clock_monotonic_raw:" in line:
                clock_monotonic_raw = int(line.strip().split(": ")[1])
    if cntvct == 0 or clock_monotonic_raw == 0:
        raise ValueError(f"Failed to find 'cntvct' or 'clock_monotonic_raw' in {config_path}, please check.")
    return cntvct, clock_monotonic_raw


def load_start_time(start_info_path):
    file_description = os.open(start_info_path, os.O_RDONLY)
    with os.fdopen(file_description, 'r') as info:
        data = json.load(info)
        if 'collectionTimeBegin' not in data:
            raise ValueError(f"Invalid or missing 'CPU' data in {start_info_path}.")
        collection_time_begin = float(data['collectionTimeBegin'])
    return collection_time_begin


def create_span_message_dict(data):
    span_msg_dict = {}
    for cur in data:
        if len(cur) < 6:
            continue

        msg = cur[6]
        if not (msg.startswith("span=") and "*" in msg):
            continue

        span_msg, msg = msg.split("*", 1)
        span_id = span_msg.split("=", 1)[-1]  # "=" is within "span="
        span_msg_dict.setdefault(span_id, []).append((cur, msg))

    message_dict = {}
    for span_id, cur_msg in span_msg_dict.items():
        cur_msg.sort(key=lambda xx: xx[0][3])  # Sort by cur, guaranteed longer than 6
        message_dict[span_id] = "".join((xx[1] for xx in cur_msg))
    return message_dict


def load_tx_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM MsprofTxEx")
    all_data = cursor.fetchall()

    columns = [description[0] if description[0] != "message" else "ori_msg" for description in cursor.description]
    if "mark_id" not in columns:
        raise ValueError(f'"mark_id" not exists in database: {db_path}, All columns: {columns}')
    columns += ["message"]
    message_dict = create_span_message_dict(all_data)

    basic_df_list, message_df_list = [], []
    for cur in all_data:
        if len(cur) < 6 or cur[6].startswith("span="):
            continue
        msg = "" if cur[2] == "start/end" else cur[6]  # clean span name in range
        msg_combined = (msg + message_dict.get(str(cur[5]), "")).replace("^", "\"")
        if not (msg_combined.startswith('{') and msg_combined.endswith('}')):
            msg_combined = '{' + msg_combined[:-1] + '}'  # -1 is ,
        msg_combined_json = json.loads(msg_combined)

        basic_df_list.append(cur + (msg_combined_json,))  # also append raw dict message
        message_df_list.append(msg_combined_json)

    basic_df = pd.DataFrame(basic_df_list, columns=columns)
    message_df = pd.DataFrame(message_df_list)
    all_data_df = pd.concat([basic_df, message_df], axis=1)
    all_data_df["span_id"] = all_data_df["mark_id"]
    conn.close()
    return all_data_df


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


def load_memory_data(db_path):
    if db_path is None:
        return None
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM MemUsage
    """)

    data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    df = pd.DataFrame(data, columns=columns)
    conn.close()
    return df


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


def load_time_info(filepaths):
    cntvct, clock_monotonic_raw = load_start_cnt(filepaths.get("host_start"))
    cpu_frequency = load_cpu_freq(filepaths.get("info"))
    collection_time_begin = load_start_time(filepaths.get("start_info"))
    return dict(
        cntvct=cntvct,
        clock_monotonic_raw=clock_monotonic_raw,
        collection_time_begin=collection_time_begin,
        cpu_frequency=cpu_frequency
    )


def load_prof(filepaths):
    tx_data_df = load_tx_data(filepaths.get("tx"))
    cpu_data_df = load_cpu_data(filepaths.get("cpu"))
    memory_data_df = load_memory_data(filepaths.get("memory"))
    time_info = load_time_info(filepaths)

    return dict(
        tx_data_df=tx_data_df,
        cpu_data_df=cpu_data_df,
        memory_data_df=memory_data_df,
        time_info=time_info,
    )


def read_origin_db(db_path: str):
    file_filter = {
        "tx": "msproftx.db",
        "cpu": "host_cpu_usage.db",
        "memory": "host_mem_usage.db",
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
    if not data:
        logger.info("Read origin db %s is empty, please check.", input_path)
        return
    logger.info('Read origin db success.')

    all_plugins = sort_plugins(builtin_plugins + custom_plugins)
    total_plugins = len(all_plugins)
    for cur_id, plugin in enumerate(all_plugins):
        try:
            data = plugin.parse(data)
            logger.info(f'[{cur_id + 1}/{total_plugins}] {plugin.name} success.')
        except ParseError as ex:
            if plugin.name in ['plugin_timestamp', 'plugin_concat']:
                logger.exception(f'{plugin.name} failure. Program stopped.')
                return
            else:
                logger.exception(f'{plugin.name} failure. Skip it.')
        except Exception as ex:
            logger.exception(f'{plugin.name} failure. Skip it.')

    logger.info('Starting exporter processes.')
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(exporter.export, data) for exporter in exporters]
        for future in futures:
            try:
                future.result()
            except Exception as e:
                pass  # Do nothing
    logger.info('Exporter done.')
