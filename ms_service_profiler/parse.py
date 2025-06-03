# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import argparse
import subprocess
from pathlib import Path
import json
import re
import sqlite3
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from json import JSONDecodeError

import pandas as pd

from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.constant import US_PER_SECOND, MSPROF_REPORTS_PATH
from ms_service_profiler.plugins import builtin_plugins, custom_plugins, PluginMsptiProcess
from ms_service_profiler.plugins.sort_plugins import sort_plugins
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import ParseError, LoadDataError
from ms_service_profiler.utils.file_open_check import FileStat
from ms_service_profiler.utils.file_open_check import ms_open
from ms_service_profiler.exporters.utils import (
    create_sqlite_db, check_input_path_valid, check_output_path_valid,
    find_file_in_dir, delete_dir_safely, create_sqlite_tables
)


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
        if 'collectionTimeBegin' not in data or 'clockMonotonicRaw' not in data:
            raise ValueError(f"Invalid or missing 'CPU' data in {start_info_path}.")
        collection_time_begin = float(data['collectionTimeBegin'])
        clock_monotonic_raw = float(data['clockMonotonicRaw'])
    return collection_time_begin, clock_monotonic_raw


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
    if db_path is None:
        return None
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT pid, tid, event_type, start_time, end_time, mark_id, message "
        "FROM MsprofTxEx order by start_time "
    )
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
        cpu_frequency = cpu_data.get('Frequency', 0)
        if cpu_frequency != "":
            return float(cpu_frequency) * US_PER_SECOND

    logger.warning(f"Missing 'Frequency' value in 'CPU' data.")
    return 0

def handle_other_wildcard_patterns(folder_path, pattern, alias, filepaths):
    for fp in Path(folder_path).rglob(pattern):
        filepaths[alias] = str(fp)
        break
    return filepaths


def get_filepaths(folder_path, file_filter):
    filepaths = {}
    reverse_d = {value: key for key, value in file_filter.items()}
    wildcard_patterns = [p for p in reverse_d.keys() if "*" in p or "?" in p]

    # 精确匹配的文件路径
    filepaths = handle_exact_match(folder_path, reverse_d)

    # 创建映射
    pattern_handlers = {
        "msprof_*.json": handle_msprof_pattern,
        "ms_service_*.db": handle_service_pattern
    }

    # 通配符匹配的文件路径
    for pattern in wildcard_patterns:
        alias = reverse_d[pattern]
        handler = pattern_handlers.get(pattern, handle_other_wildcard_patterns)
        filepaths = handler(folder_path, alias, filepaths)

    return filepaths


def handle_exact_match(folder_path, reverse_d):
    filepaths = {}
    for fp in Path(folder_path).rglob('*'):
        if fp.name in reverse_d:
            filepaths[reverse_d[fp.name]] = str(fp)
    return filepaths

def handle_service_pattern(folder_path, alias, filepaths):
    # regex_pattern = r'^ms_service_[\w.-]+.db'
    regex_pattern = r'^ms_service_[\w.-]+.db'
    matched_files = []
    for fp in Path(folder_path).rglob('*.db'):
        if re.match(regex_pattern, fp.name):
            matched_files.append(str(fp))
    if matched_files:
        if alias not in filepaths:
            filepaths[alias] = []
        filepaths[alias].extend(matched_files)
    return filepaths


def handle_msprof_pattern(folder_path, alias, filepaths):
    regex_pattern = r'^msprof_\d+\.json$'
    matched_files = []
    for fp in Path(folder_path).rglob('*.json'):
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
    cntvct, host_clock_monotonic_raw = load_start_cnt(filepaths.get("host_start"))
    cpu_frequency = load_cpu_freq(filepaths.get("info"))
    collection_time_begin, start_clock_monotonic_raw = load_start_time(filepaths.get("start_info"))
    return dict(
        cntvct=cntvct,
        host_clock_monotonic_raw=host_clock_monotonic_raw,
        collection_time_begin=collection_time_begin,
        start_clock_monotonic_raw=start_clock_monotonic_raw,
        cpu_frequency=cpu_frequency
    )


def load_host_name(tx_data_df, info_path):
    cpu_frequency = None
    with ms_open(info_path, 'r') as info:
        try:
            data = json.load(info)
        except JSONDecodeError as ex:
            logger.error(f"file {info_path} is not a json file. ")
            data = {
                "hostname": "",
                "hostUid": ""
            }
        host_name = data.get("hostname")
        host_uid = data.get("hostUid")
    
    tx_data_df["hostname"] = host_name
    tx_data_df["hostuid"] = host_uid


def load_prof(filepaths):
    tx_data_df = load_tx_data(filepaths.get("tx"))
    cpu_data_df = load_cpu_data(filepaths.get("cpu"))
    memory_data_df = load_memory_data(filepaths.get("memory"))
    time_info = load_time_info(filepaths)
    msprof_files = filepaths.get("msprof", [])
    if tx_data_df is not None:
        load_host_name(tx_data_df, filepaths.get("info"))

    return dict(
        tx_data_df=tx_data_df,
        cpu_data_df=cpu_data_df,
        memory_data_df=memory_data_df,
        time_info=time_info,
        msprof_data=msprof_files
    )


def get_mspti_db_filepaths(folder_path):
    filepaths = []
    # 合并后的正则表达式，同时验证文件名格式和提取通配符内容
    unified_pattern = re.compile(r'^ascend_service_profiler_(.+)\.db$')

    for fp in Path(folder_path).rglob('*'):  # 遍历所有文件
        match = unified_pattern.match(fp.name)
        if fp.is_file() and match:
            filepaths.append((str(fp), match.group(1)))
    return filepaths


def read_mspti_db(input_path):
    paths_and_pid = get_mspti_db_filepaths(input_path)
    data_list = []
    for db_path, db_id in paths_and_pid:
        try:
            api_df, kernel_df = load_ops_db(db_path, db_id)
            data_list.append(
                dict(
                    api_df=api_df,
                    kernel_df=kernel_df,
                    db_id=db_id
                )
            )
        except Exception as ex:
            raise LoadDataError(db_path) from ex
    return data_list


def load_ops_db(filepath, db_id):
    with sqlite3.connect(filepath) as conn:
        api_query = """
        SELECT name, start, end, processId, threadId, correlationId FROM Api order by correlationId asc
        """
        kernel_query = """
        SELECT name, type, start, end, deviceId, streamId, correlationId FROM Kernel order by correlationId asc
        """
        api_df = pd.read_sql_query(api_query, conn)
        kernel_df = pd.read_sql_query(kernel_query, conn)
        api_df["db_id"] = db_id
        kernel_df["db_id"] = db_id
    return api_df, kernel_df


def check_sub_profiler_path(input_path):
    # 判断子目录是否有PROF文件夹 如果有则走原来解析逻辑返回True 如果没有尝试走mspti返回False
    input_path = Path(input_path)
    for fp in Path(input_path).rglob('**'):
        if "PROF_" in fp.name:
            return True
    for fp in input_path.glob('*'):
        if "ms_service" in fp.name:
            return True  # 存在文件名包含'ms_service'的文件
    return False


@timer(logger.info)
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

    '''
    data是各PROF文件夹下的数据构成的列表
    time_info: 包含 info.json, start_info, host_start 文件信息
               info.json: Frequency(CPU 频率)
               start_info: collectionTimeBegin(起始时间戳, 只有这个是us级, 其他都为ns级), clockMonotonicRaw(逻辑时钟计数)
               host_start: cntvct(起始时间计数), clock_monotonic_raw(逻辑时钟计数)
    时间戳计算方法: 1. Frequency能正常获取, 则 
        [(当前计数 - cntvct) / Frequency * NS_PER_SECOND + 
            clock_monotonic_raw - clockMonotonicRaw] / NS_PER_US + collectionTimeBegin
                   2. Frequency不能正常获取, 则
        [当前计数 - clockMonotonicRaw] / NS_PER_US + collectionTimeBegin
    '''
    for dp in Path(db_path).glob("**/PROF_*"):
        filepaths = get_filepaths(dp, file_filter)
        try:
            data = load_prof(filepaths)
            data_list.append(data)
        except Exception as ex:
            raise LoadDataError(str(dp)) from ex

    data = load_service_data(db_path)
    data_list.append(data)
    return data_list


def parse(input_path, plugins, exporters, **kwargs):
    # Compatible with blue zone calls
    parse_run(input_path=input_path, exporters=exporters, args=kwargs.get("args"))


def parse_run(input_path, exporters, args=None):
    logger.info('Start to parse.')

    is_msprof_data = check_sub_profiler_path(input_path)

    # 加载原始db数据
    if is_msprof_data:
        data = read_origin_db(input_path)
    else:
        data = read_mspti_db(input_path)
    if not data:
        logger.info("Read origin db %s is empty, please check.", input_path)
        return
    logger.info('Read origin db success.')

    if is_msprof_data:
        from ms_service_profiler.pipeline import PipelineService
        pipeline = PipelineService(args)
        pipeline.set_depends_result("data_source:msprof", data)
        data = pipeline.run()
    else:
        data = PluginMsptiProcess.parse(data)

    logger.info('Starting exporter processes.')
    futures = {exporter.name: exporter.export(data) for exporter in exporters}

    logger.info('Exporter done.')


def gen_msprof_command(full_path):
    if len(full_path.split()) != 1:
        raise ValueError(f"{full_path} is invalid.")

    config_path = os.path.join(os.path.dirname(__file__), "config", MSPROF_REPORTS_PATH)
    if not os.path.isfile(config_path):
        logger.error("File not found: %r, please re-install the ascend-toolkit", config_path)
        raise OSError

    command = f"msprof --export=on --reports={config_path} --output={full_path}"
    logger.debug("command: %s", command)
    return command


def run_msprof_command(command):
    command_list = command.split()
    try:
        subprocess.run(command_list, stdout=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"msprof error: {e}")
    except Exception as e:
        logger.error(f"msprof error occurred: {e}")


def clear_last_msprof_output(full_path):
    # 调用msprof前删除mindstudio_profiler_output文件夹
    msprof_output_path = os.path.join(full_path, 'mindstudio_profiler_output')
 
    #  如果不存在mindstudio_profiler_output文件夹，则不需要清理
    if not os.path.isdir(msprof_output_path):
        return
 
    delete_dir_safely(msprof_output_path)


def is_need_msprof(full_path):
    if not find_file_in_dir(full_path, 'msproftx.db'):
        return True

    msprof_output_path = os.path.join(full_path, 'mindstudio_profiler_output')
    if not os.path.isdir(msprof_output_path):
        return True

    return False


def preprocess_prof_folders(input_path, max_parallel=8):
    if not check_sub_profiler_path(input_path):
        return False
    msprof_commnds = []
    for root, dirs, _ in os.walk(input_path):
        for dir_name in dirs:
            full_path = os.path.join(root, dir_name)
            try:
                FileStat(full_path)
            except Exception as err:
                raise argparse.ArgumentTypeError(f"msprof path:{full_path} is illegal. Please check.") from err

            if dir_name.startswith('PROF_') and is_need_msprof(full_path):
                command = gen_msprof_command(full_path)
                logger.info(f"{command}")
                clear_last_msprof_output(full_path)
                msprof_commnds.append(command)

    with ProcessPoolExecutor(max_workers=min(max_parallel, os.cpu_count() or max_parallel)) as executor:
        futures = {cmd: executor.submit(run_msprof_command, cmd) for cmd in msprof_commnds}
        for cmd, future in futures.items():
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error executing cmd: {cmd}, message: {e}")

    if not find_file_in_dir(input_path, 'msproftx.db'):
        input_path = Path(input_path)
        for fp in input_path.glob('*'):
            if "ms_service" in fp.name:
                return True
        raise ValueError("msprof failed! No msproftx.db file is generated.")
    return True


def load_service_data(db_path: str):
    file_filter = {
        "service": "ms_service_*.db"
    }

    filepaths = get_filepaths(db_path, file_filter)
    try:

        hello_files = filepaths.get("service", [])
    except Exception as ex:
        raise LoadDataError(str(db_path)) from ex

    db_dict = {}
    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    data_list = []

    data_frame = pd.DataFrame()

    return process(hello_files)


    for db_path in hello_files:
        conn = sqlite3.connect(db_path)
        conn.row_factory = dict_factory
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM mstx order by markId, flag")
        except sqlite3.OperationalError as e:
            logger.warning("%s: %r", e, db_path)
            continue

        mstx = cursor.fetchall()

        try:
            cursor.execute("SELECT * FROM meta")
        except sqlite3.OperationalError as e:
            logger.warning("%s: %r", e, db_path)
            continue

        meta_datas = cursor.fetchall()
        mstx_deal = {}

        for x in mstx:
            mark_id = x.get("markId")
            flag = x.get("flag")
            mstx_deal.setdefault(mark_id, {"markID": mark_id, "processId": x.get("processId"),
                                           "threadId": x.get("threadId"), "flag": flag})
            info = mstx_deal.get(mark_id)

            for meta in meta_datas:
                print(f"info[{meta.get('name')}]: {meta.get('value')}")
                info[meta.get("name")] = meta.get("value")

            timestamp = x.get("timestamp")
            if flag == 2:
                info["start"] = timestamp
                info["name"] = x.get("name")
            elif flag == 4:
                info["end"] = timestamp
            else:
                name : str = x.get("name")
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

        df['event_type'] = df['flag'].replace({
            1: "marker", 2: 'start/end'
        })
        df.rename(columns={'start': 'start_time'}, inplace=True)
        df.rename(columns={'end': 'end_time'}, inplace=True)

        import datetime

        from ms_service_profiler.constant import US_PER_SECOND, NS_PER_US
        def timestamp_converter(timestamp):
            try:
                date_time = datetime.datetime.fromtimestamp(timestamp / US_PER_SECOND)
                return date_time.strftime("%Y-%m-%d %H:%M:%S:%f")
            except Exception as ex:
                return str(timestamp)

        df['start_time'] = df['start_time'] / 1000
        df['end_time'] = df['end_time'] / 1000
        df['during_time'] = df['end_time'] - df['start_time']
        df['start_datetime'] = df['start_time'].apply(timestamp_converter)
        df['end_datetime'] = df['end_time'].apply(timestamp_converter)
        df.rename(columns={'msg': 'message'}, inplace=True)

        data_frame = pd.concat([data_frame, df], axis=0)

        db_dict[os.path.splitext(os.path.basename(db_path))[0]] = dict(mstx=list(mstx_parse_msg.values()))

    message_df = pd.json_normalize(data_frame['message'])
    data_frame = data_frame.reset_index(drop=True)
    all_data_df = pd.concat([data_frame, message_df], axis=1)
    all_data_df["span_id"] = all_data_df["mark_id"]
    all_data_df = all_data_df.loc[:, ~all_data_df.columns.duplicated(keep='first')]


    all_data_df['start_time'] = all_data_df['start_time'].fillna(all_data_df['end_time'])


    data_list = dict(tx_data_df=all_data_df, cpu_data_df=None, memory_data_df=None, time_info=None, msprof_data=[], msprof_data_df=[])
    return db_dict, data_list


def process(files):
    from ms_service_profiler.parse_helper.utils import convert_db_to_df, convert_timestamp

    df = convert_db_to_df(files)
    df = df.reset_index(drop=True).rename(columns={'timestamp': 'start_time', 'endTimestamp': 'end_time'})
    df[['start_time', 'end_time']] = df[['start_time', 'end_time']].div(1000)
    df['during_time'] = df['end_time'] - df['start_time']
    df['start_datetime'] = pd.to_datetime(df['start_time'], unit='us', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime("%Y-%m-%d %H:%M:%S:%f")
    df['end_datetime'] = pd.to_datetime(df['end_time'], unit='us', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime("%Y-%m-%d %H:%M:%S:%f")

    df['message'] = df['message'].str.replace(r'\^', '"', regex=True).where(lambda s: s.str.match(r'^{.*}$'), other=lambda s: "{" + s.str.replace(r",$", "", regex=True) + "}").apply(json.loads)

    msg_df = pd.json_normalize(df['message'])
    all_data_df = df.join(msg_df)
    all_data_df.insert(0, 'hostuid', df['hostname'])

    return dict(tx_data_df=all_data_df, cpu_data_df=None, memory_data_df=None, time_info=None, msprof_data=[], msprof_data_df=[])


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
    parser.add_argument(
        '--format',
        nargs='+',
        default=['db', 'csv', 'json'],
        choices=['db', 'csv', 'json'],
        help='Format to save')

    args = parser.parse_args()

    # 初始化日志等级
    set_log_level(args.log_level)

    # msprof预处理
    is_msprof_data = preprocess_prof_folders(args.input_path)

    # 初始化Exporter
    if is_msprof_data:
        exporters = ExporterFactory.create_exporters(args)
    else:
        exporters = ExporterFactory.create_mspti_exporters(args)

    # 创建output目录
    Path(args.output_path).mkdir(parents=True, exist_ok=True)
    if 'db' in args.format:
        create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters, args=args)


if __name__ == '__main__':
    main()
