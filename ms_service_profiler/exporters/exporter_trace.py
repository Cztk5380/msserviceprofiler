# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import json
import os
import threading
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.file_open_check import ms_open
from ms_service_profiler.plugins.plugin_req_status import ReqStatus


class ExporterTrace(ExporterBase):
    name = "trace"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        all_data_df, cpu_data_df = data['tx_data_df'], data['cpu_data_df']
        output = cls.args.output_path
        trace_data = create_trace_events(all_data_df, cpu_data_df)
        save_trace_data_into_json(trace_data, output)


# 定义一个函数用于写文件
def write_trace_data_to_file(trace_data, output):
    with ms_open(output, "w") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)


def save_trace_data_into_json(trace_data, output):
    file_path = os.path.join(output, 'chrome_tracing.json')

    # 创建并启动新线程来执行写文件操作
    write_thread = threading.Thread(target=write_trace_data_to_file, args=(trace_data, file_path))
    write_thread.start()


def add_flow_event(flow_event_df):
    flow_event_df.loc[:, 'rid'] = flow_event_df['rid'].str.split(',')
    exploded_df = flow_event_df.explode('rid')
    exploded_df['tid'] = exploded_df['domain']
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


def create_trace_events(all_data_df, cpu_data_df):
    metric_event = ['npu', 'KVCache']
    valid_name_df = all_data_df[all_data_df['name'].notna() & (~all_data_df['domain'].isin(metric_event))]
    trace_event_df = valid_name_df.copy()

    # trace事件
    trace_event_df['ph'] = ['I' if during_time == 0 else 'X' for during_time in valid_name_df['during_time']]
    trace_event_df['ts'] = valid_name_df['start_time']
    trace_event_df['tid'] = valid_name_df['domain']
    trace_event_df['dur'] = valid_name_df['during_time']
    trace_event_df['args'] = [
        {
            'start_datetime': start,
            'end_datetime': end,
            'batch_type': batch_type,
            'batch_size': batch_size,
            'batch_info': res_list
        }
        for start, end, batch_type, batch_size, res_list in zip(
            valid_name_df['start_datetime'],
            valid_name_df['end_datetime'],
            valid_name_df['batch_type'],
            valid_name_df['batch_size'],
            valid_name_df['res_list']
        )
    ]
    trace_events = trace_event_df[['name', 'ph', 'ts', 'dur', 'pid', 'tid', 'args']].to_dict(orient='records')

    # metric事件
    cpu_trace_events = add_cpu_events(cpu_data_df)
    trace_events.extend(cpu_trace_events)
    npu_trace_events = add_npu_events(all_data_df[all_data_df['name'] == 'npu'])
    trace_events.extend(npu_trace_events)
    kv_trace_events = add_kvcache_events(all_data_df[all_data_df['domain'] == 'KVCache'])
    trace_events.extend(kv_trace_events)

    # flow事件
    flow_event_df = trace_event_df[trace_event_df['rid'].notna()]
    flow_trace_events = add_flow_event(flow_event_df)
    trace_events.extend(flow_trace_events)
    trace_events = sort_trace_events_by_tid(trace_events)

    trace_data = {"traceEvents": trace_events}
    return trace_data


def sort_trace_events_by_tid(trace_events):
    req_status_names = list(ReqStatus.__members__.keys())
    tid_sorting_order = ['http', 'Queue'] + req_status_names + ['BatchSchedule', 'modelExec']
    main_pid = 0
    for event_info in trace_events:
        if event_info.get("cat") in tid_sorting_order:
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


def add_cpu_events(cpu_data_df):
    cpu_trace_df = cpu_data_df.copy()
    cpu_trace_df['name'] = 'CPU Usage'
    cpu_trace_df['ph'] = 'C'
    cpu_trace_df['ts'] = cpu_data_df['start_time']
    cpu_trace_df['pid'] = 1
    cpu_trace_df['tid'] = 'CPU Usage'
    cpu_trace_df['args'] = [{'CPU Usage': usage} for usage in cpu_data_df['usage']]
    cpu_trace_events = cpu_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return cpu_trace_events


def add_npu_events(npu_data_df):
    npu_trace_df = npu_data_df.copy()
    npu_trace_df['name'] = 'NPU Usage'
    npu_trace_df['ph'] = 'C'
    npu_trace_df['ts'] = npu_data_df['start_time']
    npu_trace_df['tid'] = 'NPU Usage'
    npu_trace_df['args'] = [{'Usage': usage} for usage in npu_data_df['usage=']]
    npu_trace_events = npu_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return npu_trace_events


def add_kvcache_events(kv_data_df):
    kv_trace_df = kv_data_df.copy()
    kv_trace_df['name'] = kv_data_df['domain']
    kv_trace_df['ph'] = 'C'
    kv_trace_df['ts'] = kv_data_df['start_time']
    kv_trace_df['tid'] = kv_data_df['domain']
    kv_trace_df['args'] = [{'Device Block': usage} for usage in kv_data_df['deviceBlock=']]
    kv_trace_events = kv_trace_df[['name', 'ph', 'ts', 'pid', 'tid', 'args']].to_dict(orient='records')
    return kv_trace_events
