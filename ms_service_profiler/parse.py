# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import fnmatch
import os
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import json
import re
import sqlite3
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.exporters.utils import create_sqlite_db, check_input_path_valid, check_output_path_valid
from ms_service_profiler.constant import US_PER_SECOND
from ms_service_profiler.plugins import builtin_plugins, custom_plugins
from ms_service_profiler.plugins.sort_plugins import sort_plugins
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.utils.error import ParseError, LoadDataError
from ms_service_profiler.utils.file_open_check import FileStat
from ms_service_profiler.utils.check.rule import Rule


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
    wildcard_patterns = [p for p in reverse_d.keys() if "*" in p or "?" in p]

    # 处理精确匹配的文件
    for fp in Path(folder_path).rglob('*'):
        if fp.name in reverse_d:
            filepaths[reverse_d[fp.name]] = str(fp)

    # 处理通配符匹配的文件
    for pattern in wildcard_patterns:
        alias = reverse_d[pattern]
        if pattern == "msprof_*.json":
            # 使用正则表达式进行精确匹配
            regex_pattern = r'^msprof_\d+\.json$'
            matched_files = []
            for fp in Path(folder_path).rglob('*.json'):
                if re.match(regex_pattern, fp.name):
                    matched_files.append(str(fp))
            if matched_files:
                if alias not in filepaths:
                    filepaths[alias] = []
                filepaths[alias].extend(matched_files)
        else:
            # 原有逻辑处理其他通配符模式
            for fp in Path(folder_path).rglob(pattern):
                filepaths[alias] = str(fp)
                break  # 保持原有逻辑，只取第一个匹配的文件

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
    msprof_files = filepaths.get("msprof", [])
    msprof_data = [load_single_prof(pf) for pf in msprof_files]

    return dict(
        tx_data_df=tx_data_df,
        cpu_data_df=cpu_data_df,
        memory_data_df=memory_data_df,
        time_info=time_info,
        msprof_data=msprof_data
    )


def load_single_prof(pf):
    try:
        with open(pf, 'r', encoding='utf-8') as file:
            trace_events = json.load(file)

        # 找到 CANN 进程的 pid
        cann_pid = None
        for event in trace_events:
            if event.get("name") == "process_name":
                args = event.get("args", {})
                if args.get("name") == "CANN":
                    cann_pid = event.get("pid")
                    break

        if cann_pid is None:
            return {"traceEvents": []}

        # 筛选出 CANN 相关的事件
        def is_cann_event(event):
            return event.get("pid") == cann_pid

        filtered_trace_events = [
            event
            for event in trace_events
            if is_cann_event(event)
        ]

        # 创建包含筛选后 CANN 事件的字典
        merged_dict = {
            "traceEvents": filtered_trace_events
        }
        return merged_dict
    except FileNotFoundError:
        logger.warning("The file was not found. Please check the file path.")
        return {"traceEvents": []}
    except json.JSONDecodeError:
        logger.warning("The file {pf} is not in a valid JSON format.")
        return {"traceEvents": []}


def read_origin_db(db_path: str):
    file_filter = {
        "tx": "msproftx.db",
        "cpu": "host_cpu_usage.db",
        "memory": "host_mem_usage.db",
        "host_start": "host_start.log",
        "info": "info.json",
        "start_info": "start_info",
        "msprof": "msprof_*.json"
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


def parse(input_path, plugins, exporters):
    logger.info('Start to parse.')
    # 解析数据
    data = read_origin_db(input_path)
    if not data:
        logger.info("Read origin db %s is empty, please check.", input_path)
        return
    logger.info('Read origin db success.')

    all_plugins = sort_plugins(builtin_plugins + plugins)
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


def gen_msprof_command(full_path):
    try:
        FileStat(full_path)
    except Exception as err:
        raise argparse.ArgumentTypeError(f"input path:{full_path} is illegal. Please check.") from err

    command = "msprof --export=on "
    output_param = f"--output={full_path}"
    return command + output_param


def find_file_in_dir(directory, filename):
    count = 0
    max_iter = 1000

    for _, _, files in os.walk(directory):
        count += len(files)
        if count > max_iter:
            break
        if filename in files:
            return True
    return False


def run_msprof_command(command):
    command_list = command.split()
    try:
        subprocess.run(command_list, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"msprof error: {e}")
    except Exception as e:
        logger.error(f"msprof error occurred: {e}")


def preprocess_prof_folders(input_path):
    for root, dirs, _ in os.walk(input_path):
        for dir_name in dirs:
            full_path = os.path.join(root, dir_name)

            if dir_name.startswith('PROF_') and not find_file_in_dir(full_path, 'msproftx.db'):
                command = gen_msprof_command(full_path)
                logger.info(f"{command}")
                run_msprof_command(command)
    if not find_file_in_dir(input_path, 'msproftx.db'):
        raise ValueError("msprof failed! No msproftx.db file is generated.")


def main():
    parser = argparse.ArgumentParser(description='MS Server Profiler')
    parser.add_argument(
        '--input-path',
        required=True,
        type=check_input_path_valid,
        help='Path to the folder containing profile data.')
    parser.add_argument(
        '--output-path',
        type=check_output_path_valid,
        default=os.path.join(os.getcwd(), 'output'),
        help='Output file path to save results.')
    parser.add_argument(
        '--log-level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        help='Log level to print')

    args = parser.parse_args()

    # 初始化日志等级
    set_log_level(args.log_level)

    # msprof预处理
    preprocess_prof_folders(args.input_path)

    # 初始化Exporter
    exporters = ExporterFactory.create_exporters(args)

    # 创建output目录
    Path(args.output_path).mkdir(parents=True, exist_ok=True)
    create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters)


if __name__ == '__main__':
    main()
