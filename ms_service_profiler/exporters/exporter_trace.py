# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from ms_service_profiler.exporters.base import TaskExporterBase
from ms_service_profiler.utils.file_open_check import ms_open, safe_json_dump, OpenException
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import DatabaseError
from ms_service_profiler.exporters.utils import get_db_connection, create_sqlite_tables
from ms_service_profiler.utils.trace_to_db import (
    trans_trace_event, save_cache_data_to_db, TRACE_TABLE_DEFINITIONS
)


class ExporterTrace(TaskExporterBase):
    name = "trace"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def depends(cls):
        return ["pipeline:service", "pipeline:mspti"]

    def do_export(self):
        self.export(self.get_depends_result("pipeline:service"), self.get_depends_result("pipeline:mspti"))

    @classmethod
    @timer(logger.info)
    def export(cls, data, mspti) -> None:
        if 'db' not in cls.args.format and 'json' not in cls.args.format:
            return

        output = cls.args.output_path

        cpu_data_df, memory_data_df = data['cpu_data_df'], data['memory_data_df']
        all_data_df = data['tx_data_df'].copy()
        if 'pid_label_map' in data:
            pid_label_map = data['pid_label_map']
        else:
            pid_label_map = None
        all_data_df['domain'] = all_data_df['domain'].replace('PDSplit', 'PDCommunication')
        msprof_data_df = data['msprof_data']

        cann_data = [load_single_prof(pf, index) for index, pf in enumerate(msprof_data_df)]
        trace_data = create_trace_events(all_data_df, cpu_data_df, memory_data_df, pid_label_map)
        merged_data = merge_json_data(trace_data, cann_data)

        api_df = pd.DataFrame()
        kernel_df = pd.DataFrame()

        if mspti is not None:
            api_df = mspti.get('api_df', pd.DataFrame())
            kernel_df = mspti.get('kernel_df', pd.DataFrame())

        if not api_df.empty or not kernel_df.empty:

            tarce_events_list = []

            api_events = export_event_from_df(api_df, "Api", "Api")
            tarce_events_list.extend(api_events)

            kernel_events = export_event_from_df(kernel_df, "Kernel", "Kernel")
            tarce_events_list.extend(kernel_events)

            mspti_data = {"traceEvents": tarce_events_list}
            merged_data = merge_json_data(merged_data, [mspti_data])

        if 'json' in cls.args.format:
            save_trace_data_into_json(merged_data, output)

        if 'db' in cls.args.format:
            logger.info('Start write trace data to db')
            create_sqlite_tables(TRACE_TABLE_DEFINITIONS)
            save_trace_data_into_db(merged_data)
            logger.info('Write trace data to db success')


def process_prof_trace_events(events, index):
    for event in events:
        event_id = event.get('id')
        event_ph = event.get('ph')
        if event_id is not None and event_ph in ['s', 'f']:
            # 将 event_id 和 index 转换为字符串并拼接，保证不会重复
            event['id'] = str(event_id) + '_' + str(index)
    return events


def load_single_prof(pf, prof_id):
    try:
        with ms_open(pf, 'r', encoding='utf-8', max_size=-1) as file:
            trace_events = json.load(file)
    except OpenException as oe:
        logger.warning(f"OpenException occurred {oe}")
        return {"traceEvents": []}
    except FileNotFoundError:
        logger.warning("The msprof.json file was not found. Please check the file path.")
        return {"traceEvents": []}
    except json.JSONDecodeError:
        logger.warning(
            "%r is not in a valid JSON format, " \
            "which might be normal and probably because this file stores 'mstx' data only",
            pf
        )
        return {"traceEvents": []}

    trace_events = process_prof_trace_events(trace_events, prof_id)

    return {"traceEvents": trace_events}


def find_cann_pid(trace_events):
    for event in trace_events:
        if event.get("name") == "process_name":
            args = event.get("args", {})
            if args.get("name") == "CANN":
                return event.get("pid")
    return None


def save_trace_data_into_db(trace_data):
    events = trace_data.get("traceEvents", [])
    try:
        # 创建数据库连接
        conn = get_db_connection()
        cursor = conn.cursor()

        # 写入db文件
        for event in events:
            trans_trace_event(event, cursor)

        # 写入批量提交后剩余的缓存数据
        save_cache_data_to_db(cursor)

        conn.commit()
    except Exception as ex:
        conn.rollback()  # 失败时回滚
        raise DatabaseError("Cannot update sqlite database when create trace table.") from ex
    finally:
        if conn:
            conn.close()


def merge_json_data(trace_data, msprof_data_df):
    for item in msprof_data_df:
        events = item.get("traceEvents", [])
        trace_data["traceEvents"].extend(events)
    return trace_data


@timer(logger.info)
def write_trace_data_to_file(trace_data, output):
    def write_trace_data(range_index):
        start_index, end_index = range_index
        trace_data_list = trace_data[start_index:end_index]
        return safe_json_dump(trace_data_list, ensure_ascii=False)

    gourp_count = 100000
    data_count = len(trace_data)
    group_range_list = [(x, min(x + gourp_count, data_count)) for x in range(0, data_count, gourp_count)]
    results = []
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(write_trace_data, x) for x in group_range_list]
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Error raise from exporter trace, json dump failed. message: {e}")

    with ms_open(output, "w") as f:
        f.write('{"traceEvents":[')
        for index, content2 in enumerate(results):
            if len(content2) < 2:   # 确保至少有 2 个字符
                continue
            f.write(content2[1:-1]) # 去除首字符和尾字符
            if index != len(results) - 1:
                f.write(',')

        f.write("]}")

    logger.info(f"Written trace data successfully. at {output}")


def save_trace_data_into_json(trace_data, output):
    file_path = os.path.join(output, 'chrome_tracing.json')

    write_trace_data_to_file(trace_data.get("traceEvents", []), file_path)


def add_flow_event(flow_event_df):
    flow_event_df.loc[:, 'rid'] = flow_event_df['rid'].str.split(',')
    exploded_df = flow_event_df.explode('rid')
    exploded_df['tid'] = exploded_df['domain']
    if 'PDCommunication' in flow_event_df['domain'].values:
        exploded_df['ph'] = [
            's' if 'httpReq' in name else ('f' if ('httpRes' in name and 'receiveToken=' in message) else 't')
            for name, message in zip(exploded_df['name'], exploded_df['message'])
        ]
    else:
        exploded_df['ph'] = [
            's' if 'httpReq' in name else ('f' if 'httpRes' in name else 't')
            for name in exploded_df['name']
        ]
    exploded_df['bp'] = ['b' if 'httpRes' in name else '' for name in exploded_df['name']]
    exploded_df['name'] = 'flow_' + exploded_df['rid']
    exploded_df['ts'] = exploded_df['start_time']
    exploded_df['id'] = exploded_df['rid']
    exploded_df['cat'] = exploded_df['rid']
    exploded_df['pid'] = exploded_df['pid']
    flow_trace_events = exploded_df[['name', 'ph', 'ts', 'id', 'cat', 'pid', 'tid']].to_dict(orient='records')
    return flow_trace_events


def create_trace_events(all_data_df, cpu_data_df, memory_data_df, pid_label_map=None):
    metric_event = ['npu', 'KVCache', 'PullKVCache']

    # 普通事件
    valid_name_df = all_data_df[all_data_df['name'].notna() & (~all_data_df['domain'].isin(metric_event))]
    trace_events = add_trace_events(valid_name_df)

    # metric事件
    cpu_trace_events = add_cpu_events(cpu_data_df)
    trace_events.extend(cpu_trace_events)

    mem_trace_events = add_mem_events(memory_data_df)
    trace_events.extend(mem_trace_events)

    npu_trace_events = add_npu_events(all_data_df[all_data_df['name'] == 'npu'])
    trace_events.extend(npu_trace_events)

    kv_trace_events = add_kvcache_events(all_data_df[all_data_df['domain'] == 'KVCache'])
    trace_events.extend(kv_trace_events)

    pull_kvcache_events = add_pull_kvcache_events(all_data_df[all_data_df['domain'] == 'PullKVCache'])
    trace_events.extend(pull_kvcache_events)

    # flow事件
    flow_event_df = valid_name_df[valid_name_df['rid'].notna()]
    flow_trace_events = add_flow_event(flow_event_df)
    trace_events.extend(flow_trace_events)
    trace_events = sort_trace_events_by_tid(trace_events)
    if pid_label_map is not None:
        trace_events.extend(sort_trace_events_by_pid(pid_label_map))

    trace_data = {"traceEvents": trace_events}
    return trace_data


def sort_trace_events_by_pid(pid_label_map):
    pid_sorting_meta = []
    pid_sorting = []
    for pid, item in pid_label_map.items():
        host_name = item.get("hostname", "")
        dp = item.get("dp", -1)
        pid_sorting.append((pid, host_name, dp))
    
    pid_sorting.sort(key=lambda x: (x[2], x[1]))

    for index, item in enumerate(pid_sorting):
        pid, host_name, dp = item
        pid_sorting_meta.append(dict(
            name="process_sort_index",
            ph="M",
            pid=pid,
            args=dict(sort_index=index))
        )
        if dp == -1:
            labels = [host_name]
        else:
            labels = [host_name, f"dp{int(dp)}"]
        pid_sorting_meta.append(dict(
            name="process_labels",
            ph="M",
            pid=pid,
            args=dict(labels=','.join(labels)))
        )
    
    return pid_sorting_meta


def sort_trace_events_by_tid(trace_events):
    tid_sorting_order = ['KVCache', 'Communication', 'BatchSchedule', 'ModelExecute', 'Request', 'Api', 'Kernel']
    main_pid = 0
    for event_info in trace_events:
        if event_info.get("tid") in tid_sorting_order:
            main_pid = event_info.get("pid")
            break
    tid_sorting_meta = [dict(
        name="thread_sort_index",
        ph="M",
        pid=main_pid,
        tid=tid,
        args=dict(sort_index=index)) for index, tid in enumerate(tid_sorting_order)]

    def get_tid_sorting_key(event):
        if 'tid' in event and event['tid'] in tid_sorting_order:
            return tid_sorting_order.index(event['tid'])
        else:
            return len(tid_sorting_order)

    # 排序 trace_events
    sorted_trace_events = sorted(trace_events, key=get_tid_sorting_key)

    sorted_trace_events.extend(tid_sorting_meta)
    return sorted_trace_events


def add_trace_events(valid_name_df):
    trace_event_df = valid_name_df.copy()

    # trace事件
    trace_event_df['ph'] = ['I' if during_time == 0 else 'X' for during_time in valid_name_df['during_time']]
    trace_event_df['ts'] = valid_name_df['start_time']
    trace_event_df['tid'] = valid_name_df['domain']
    trace_event_df['dur'] = valid_name_df['during_time']
    args_list = []
    for start, end, batch_type, batch_size, res_list, rid, message, tid, in zip(
            valid_name_df['start_datetime'],
            valid_name_df['end_datetime'],
            valid_name_df['batch_type'],
            valid_name_df['batch_size'],
            valid_name_df['res_list'],
            valid_name_df['rid'],
            valid_name_df['message'],
            valid_name_df['tid']
    ):
        args_dict = dict(**{k: v for k, v in message.items() if k not in ["domain", "name", "type", "rid"]}, **{
            'start_datetime': start,
            'end_datetime': end,
            'tid': tid
        })
        if batch_size is not None:
            args_dict.update({
                'batch_type': batch_type,
                'batch_size': batch_size,
            })
        if res_list is not None:
            args_dict.update({"res_list": res_list})
        if batch_size is None and rid != res_list:
            args_dict.update({"rid": rid})
        args_list.append(args_dict)
    trace_event_df['args'] = args_list
    trace_events = trace_event_df[['name', 'ph', 'ts', 'dur', 'pid', 'tid', 'args']].to_dict(orient='records')
    return trace_events


def add_cpu_events(cpu_data_df):
    if cpu_data_df is None or cpu_data_df.shape[0] == 0:
        return []
    cpu_trace_df = cpu_data_df.copy()
    cpu_trace_df['name'] = 'CPU Usage'
    cpu_trace_df['ph'] = 'C'
    cpu_trace_df['ts'] = cpu_data_df['start_time']
    cpu_trace_df['pid'] = 1
    cpu_trace_df['tid'] = 'CPU Usage'
    cpu_trace_df['args'] = [{'CPU Usage': usage} for usage in cpu_data_df['usage']]
    cpu_trace_events = cpu_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return cpu_trace_events


def add_mem_events(df):
    if df is None or df.shape[0] == 0:
        return []
    df = df.copy()
    df['name'] = 'Memory Usage'
    df['ph'] = 'C'
    df['ts'] = df['start_time']
    df['pid'] = 1
    df['tid'] = 'Memory Usage'
    df['args'] = [{'Memory Usage': usage} for usage in df['usage']]
    events = df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return events


def add_npu_events(npu_data_df):
    if npu_data_df is None or npu_data_df.shape[0] == 0:
        return []
    npu_trace_df = npu_data_df.copy()
    npu_trace_df['name'] = 'NPU Usage'
    npu_trace_df['ph'] = 'C'
    npu_trace_df['ts'] = npu_data_df['start_time']
    npu_trace_df['pid'] = 1
    npu_trace_df['tid'] = 'NPU Usage'
    npu_trace_df['args'] = [{'Usage': usage} for usage in npu_data_df['usage=']]
    npu_trace_events = npu_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return npu_trace_events


def add_kvcache_events(kv_data_df):
    if 'deviceBlock=' not in kv_data_df:
        return []
    kv_trace_df = kv_data_df.copy()
    if "scope#dp" in kv_trace_df:
        kv_trace_df['name'] = kv_trace_df['domain'] + '-dp' + kv_trace_df["scope#dp"].astype(int,
                                                                                            errors='ignore').astype(str)
    else:
        kv_trace_df['name'] = kv_trace_df['domain']
    kv_trace_df['ph'] = 'C'
    kv_trace_df['ts'] = kv_data_df['start_time']
    kv_trace_df['tid'] = kv_data_df['domain']
    kv_trace_df['args'] = [{'Device Block': usage} for usage in kv_data_df['deviceBlock=']]
    kv_trace_events = kv_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return kv_trace_events


def add_pull_kvcache_events(df):
    if df is None or df.shape[0] == 0:
        return []
    df_all_device = df.copy()
    all_events = []

    for rank in df_all_device['rank'].unique():
        rank = int(rank)
        df = df_all_device[df_all_device['rank'] == rank].copy().reset_index(drop=True)
        df['pid'] = "PullKVCache"
        df['name'] = df['domain']
        df['ph'] = 'X'
        df['ts'] = df['start_time']
        df['tid'] = f"Decode Device rank_{rank}"
        df['dur'] = df['during_time']
        args = ['rank', 'rid', 'block_tables', 'seq_len', \
                'during_time', 'start_datetime', 'end_datetime', 'start_time', 'end_time']
        df['args'] = df[[arg for arg in args if arg in df.columns]].to_dict(orient='records')
        events = df[['name', 'ph', 'ts', 'pid', 'tid', 'args', 'dur']].to_dict(orient='records')
        all_events.extend(events)

    return all_events


def export_event_from_df(df, channel_name, tid):
    tarce_events_list = []

    name_arr = df["name"].values
    start_arr = df["start"].values
    end_arr = df["end"].values
    process_arr = df["db_id"].values

    for i in range(len(df)):
        name = name_arr[i]
        start = start_arr[i] // 1000
        end = end_arr[i] // 1000
        process_id = process_arr[i]

        trace_event = {
            "name": name,
            "ph": "X",
            "ts": int(start),
            "dur": int(end - start),
            "pid": int(process_id),
            "tid": tid,
            "args": {}
        }

        tarce_events_list.append(trace_event)

    process_ids = list(set(list(process_arr)))
    for process_id in process_ids:
        channel_event = {
            "ph": "M",
            "pid": int(process_id),
            "tid": tid,
            "name": "thread_name",
            "args": {
                "name": channel_name
            }
        }
        tarce_events_list.append(channel_event)

    return tarce_events_list
