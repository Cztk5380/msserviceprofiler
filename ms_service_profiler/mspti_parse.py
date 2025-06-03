# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
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


def load_tx_data_bak(db_path):
    if db_path is None:
        return None
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT pid, tid, event_type, start_time, end_time, mark_id, message FROM MsprofTxEx")
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


def load_tx_data(db_path):
    if db_path is None:
        return None
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT processId, threadid, xx, start_time, end_time, mark_id, message FROM MsprofTxEx")
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

    # 精确匹配的文件路径
    filepaths = handle_exact_match(folder_path, reverse_d)

    # 创建映射
    pattern_handlers = {
        "hello": handle_msprof_pattern,
        "hello_*.db": handle_msprof_pattern,
    }

    # 通配符匹配的文件路径
    for pattern in wildcard_patterns:
        alias = reverse_d[pattern]
        handler = pattern_handlers.get(pattern, handle_other_wildcard_patterns)
        filepaths = handler(folder_path, alias, filepaths)
    print(filepaths)
    return filepaths


def handle_exact_match(folder_path, reverse_d):
    filepaths = {}
    for fp in Path(folder_path).rglob('*'):
        if fp.name in reverse_d:
            filepaths[reverse_d[fp.name]] = str(fp)
    return filepaths


def handle_msprof_pattern(folder_path, alias, filepaths):
    regex_pattern = r'^hello_mindie_\d+\-\d+\.db'
    matched_files = []
    for fp in Path(folder_path).rglob('*.db'):
        if re.match(regex_pattern, fp.name):
            matched_files.append(str(fp))
    if matched_files:
        if alias not in filepaths:
            filepaths[alias] = []
        filepaths[alias].extend(matched_files)
    return filepaths


def handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths):
    for fp in Path(folder_path).rglob(pattern):
        filepaths[alias] = str(fp)
        break
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

    return dict(
        tx_data_df=tx_data_df,
        cpu_data_df=cpu_data_df,
        memory_data_df=memory_data_df,
        time_info=time_info,
        msprof_data=msprof_files
    )


def read_origin_db(db_path: str):
    file_filter = {
        "hello": "hello_*.db"
    }

    data_list = []

    filepaths = get_filepaths(db_path, file_filter)
    try:

        hello_files = filepaths.get("hello", [])
    except Exception as ex:
        raise LoadDataError(str(db_path)) from ex

    db_dict = {}

    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    data_list = []
    # for x in hello_files:
    #     data_list.append(dict(tx_data_df=load_tx_data(x),
    #             msprof_data=[],
    #             msprof_data_df=[],
    #             memory_data_df=None,
    #             cpu_data_df=None,
    #             time_info=None,
    #         ))

    data_frame = pd.DataFrame()

    for db_path in hello_files:
        conn = sqlite3.connect(db_path)
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM mstx order by markId")
        mstx = cursor.fetchall()
        cursor.execute("SELECT * FROM api")
        api = cursor.fetchall()
        cursor.execute("SELECT * FROM kernel")
        kernel = cursor.fetchall()

        mstx_deal = {}
        for x in mstx:
            # print(x)
            mark_id = x.get("markId")
            flag = x.get("flag")
            mstx_deal.setdefault(mark_id, {"markID": mark_id, "processId": x.get("processId"),
                                           "threadId": x.get("threadId"), "flag": flag})
            info = mstx_deal.get(mark_id)
            timestamp = x.get("timestamp")
            if flag == 2:
                info["start"] = timestamp
                info["name"] = x.get("name")
            elif flag == 4:
                info["end"] = timestamp
            else:
                name: str = x.get("name")
                if name.startswith("span="):
                    span_msg, msg = name.split("*", 1)
                    span_id = span_msg.split("=", 1)[-1]  # "=" is within "span="
                    span_info = mstx_deal.get(int(span_id))
                    if span_info is None:
                        print(f"ERROR {db_path} {span_id} not found")
                        message = ""

                        mstx_deal.setdefault(int(span_id), {"markID": int(span_id),
                                                            "processId": x.get("processId"),
                                                            "threadId": x.get("threadId"),
                                                            "msg": msg,
                                                            "flag": flag})
                        continue
                    else:
                        message = span_info.get("msg", "")
                        message += msg
                    span_info["msg"] = message
                    del mstx_deal[mark_id]
                else:
                    info["start"] = timestamp
                    info["end"] = timestamp
                    info["msg"] = name

        mstx_parse_msg = {}

        for key, value in mstx_deal.items():
            if "end" not in value:
                continue
            msgs = value.get("msg", "")
            msgs = msgs.replace("^", "\"")
            if not (msgs.startswith('{') and msgs.endswith('}')):
                msgs = '{' + msgs[:-1] + '}'  # -1 is ,
            if msgs:
                try:
                    value["msg"] = json.loads(msgs)
                except Exception as e:
                    value["msg"] = dict(msg=msgs)
            else:
                value["msg"] = {}
            value["name"] = value["msg"].get("name", value.get("name", "XX"))
            mstx_parse_msg[key] = value

        df = pd.DataFrame(list(mstx_parse_msg.values()))

        df.rename(columns={'processId': 'pid'}, inplace=True)
        df.rename(columns={'threadId': 'tid'}, inplace=True)
        df.rename(columns={'markID': 'mark_id'}, inplace=True)

        if len(df) == 0:
            continue

        print(df.columns.to_list(), db_path)
        df['event_type'] = df['flag'].replace({
            1: "marker", 2: 'start/end'
        })
        df.rename(columns={'start': 'start_time'}, inplace=True)
        df.rename(columns={'end': 'end_time'}, inplace=True)

        import datetime

        from ms_service_profiler.constant import US_PER_SECOND, NS_PER_US
        def timestamp_converter(timestamp):
            try:
                date_time = datetime.datetime.fromtimestamp(timestamp / US_PER_SECOND / 1000)
                return date_time.strftime("%Y-%m-%d %H:%M:%S:%f")
            except Exception as ex:
                return str(timestamp)

        df['during_time'] = df['end_time'] - df['start_time']
        df['start_datetime'] = df['start_time'].apply(timestamp_converter)
        df['end_datetime'] = df['end_time'].apply(timestamp_converter)
        df.rename(columns={'msg': 'message'}, inplace=True)

        data_frame = pd.concat([data_frame, df], axis=0)

        # print(all_data_df)

        # data_list.append(dict(tx_data_df=all_data_df,
        #         msprof_data=[],
        #         msprof_data_df=[],
        #         memory_data_df=None,
        #         cpu_data_df=None,
        #         time_info=None,
        #     ))

        db_dict[os.path.splitext(os.path.basename(db_path))[0]] = dict(mstx=list(mstx_parse_msg.values()), api=api,
                                                                       kernel=kernel)

        print(len(data_frame), "  ----")

    print(data_frame)

    message_df = data_frame['message'].apply(pd.Series)
    all_data_df = pd.concat([data_frame, message_df], axis=1)
    all_data_df["span_id"] = all_data_df["mark_id"]
    all_data_df = all_data_df.loc[:, ~all_data_df.columns.duplicated(keep='first')]

    print(len(all_data_df), "  ----", all_data_df.columns.to_list())
    all_data_df = all_data_df.reset_index(drop=True)

    all_data_df['start_time'] = all_data_df['start_time'].fillna(all_data_df['end_time'])

    data_list = dict(tx_data_df=all_data_df, cpu_data_df=None, memory_data_df=None, time_info=None, msprof_data=[],
                     msprof_data_df=[])
    return db_dict, data_list


def add_flow_event(key, name, item):
    trace_event = {}
    trace_event['name'] = key + "-" + str(item.get("correlationId"))
    trace_event['ph'] = 's' if name == 'api' else 'f'
    trace_event['ts'] = item.get("end") / 1000
    trace_event['id'] = item.get("correlationId")
    trace_event['tid'] = str(item.get("threadId", f"NPU-{item.get('deviceId')}")) + "(" + name + ")"
    trace_event['pid'] = str(item.get("processId", f"{key[len('hello_mindie_'):]}-NPU-{item.get('deviceId')}"))
    trace_event['cat'] = "LOL"

    return trace_event


def add_trace(key, name, item):
    # print(item, key, name)
    try:
        msg = item.get("msg")
        start = item.get("start")
        if start is None:
            print("not found start time", key, name, item)
            if msg is None:
                msg = {}
            msg["warning"] = "not found start time"
            start = item.get("end")  # 兼容一下

        trace_event = {}
        trace_event['ph'] = 'X' if start != item.get("end") else 'I'
        trace_event['ts'] = start / 1000
        trace_event['dur'] = item.get("end") / 1000 - start / 1000
        trace_event['tid'] = str(item.get("threadId", f"NPU-{item.get('deviceId')}")) + "(" + name + ")"
        if msg is not None and msg.get("domain") == 'http':
            msg["tid"] = trace_event['tid']
            trace_event['tid'] = "http"
        trace_event['pid'] = str(item.get("processId", f"{key[len('hello_mindie_'):]}-NPU-{item.get('deviceId')}"))
        trace_event['args'] = msg
        trace_event['name'] = item.get("name", msg.get("name", "UNKNOW"))
        if trace_event['name'] == "UNKNOW":
            print("UNKNOW NAME", item, key, name)
        if trace_event['name'] == "ReqState":
            msg["tid"] = trace_event['tid']
            trace_event['tid'] = "ReqState"
        if "correlationId" in item:
            flow_event = add_flow_event(key, name, item)
            return (trace_event, flow_event)
        else:
            return (trace_event,)
    except Exception as ex:
        print(ex, key, name, item)
        return ()


def parse(input_path, output_path, exporters=None):
    logger.info('Start to parse.')
    # 解析数据
    db_dict, data = read_origin_db(input_path)
    if not db_dict:
        logger.info("Read origin db %s is empty, please check.", input_path)
        return
    logger.info('Read origin db success.')

    trace_events = []

    for key, value in db_dict.items():
        for name, span_infos in value.items():
            print("***", name)
            for span_info in span_infos:
                trace_events.extend(add_trace(key, name, span_info))

    with open(os.path.join(output_path, "chrome_trace2.json"), "w") as ff:
        json.dump(trace_events, ff)

    logger.info('Exporter chrome done.')

    all_plugins = sort_plugins(builtin_plugins[2:] + custom_plugins)
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
    # with ProcessPoolExecutor() as executor:
    #     futures = [executor.submit(exporter.export, data) for exporter in exporters]
    #     for future in futures:
    #         try:
    #             future.result()
    #         except Exception as e:
    #             print(e)
    #             pass  # Do nothing
    [exporter.export(data) for exporter in exporters]
    logger.info('Exporter done.')

    logger.info(os.path.join(output_path, "chrome_trace2.json"))


def gen_msprof_command(full_path):
    try:
        FileStat(full_path)
    except Exception as err:
        raise argparse.ArgumentTypeError(f"input path:{full_path} is illegal. Please check.") from err

    if len(full_path.split()) != 1:
        raise ValueError(f"{full_path} is invalid.")

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
        # type=check_input_path_valid,
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
    # preprocess_prof_folders(args.input_path)

    # 初始化Exporter
    exporters = ExporterFactory.create_exporters(args)

    # 创建output目录
    Path(args.output_path).mkdir(parents=True, exist_ok=True)
    create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, args.output_path, exporters)


if __name__ == '__main__':
    main()
