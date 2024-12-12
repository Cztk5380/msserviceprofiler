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

import json
import os
import stat
from ms_server_profiler.exporters.base import ExporterBase


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

def save_trace_data_into_json(trace_data, output):
    file_path = os.path.join(output, 'chrome_tracing.json')
    flags = os.O_WRONLY | os.O_CREAT
    mode = stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    file_descriptor = os.open(file_path, flags, mode)
    with os.fdopen(file_descriptor, 'w') as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)


def create_trace_events(all_data_df, cpu_data_df):
    trace_events = []

    for _, data in all_data_df.iterrows():
        if data['event_type'] == 'marker' and data['name'] is not None:
            trace_events.append(
                {
                    "name": data['name'],
                    "ph": "I",
                    "ts": data['start_time'],
                    "pid": data['pid'],
                    "tid": data['name'],
                    "cat": "Request Status",
                    "args": {**{'rid': data['rid']}, **add_args_for_state_type(data['message'])}
                },
            )
        if data['event_type'] == "start/end" and data['name'] is not None:
            trace_events.append(
                {
                    "name": data['name'],
                    "ph": "X",
                    "ts": data['start_time'],
                    "dur": data['during_time'],
                    "pid": data['pid'],
                    "tid": data['name'],
                    "cat": "Execute",
                    "args": {
                        'batchType': data['batch_type'],
                        'batchSize': data['batch_size'],
                        'rid': data['rid'],
                    }
                },
            )
        if data['rid'] is not None:
            rids = str(data["rid"]).split(",")
            for rid in rids:
                flow_event = {
                        "name": "flow_" + rid,
                        "id": rid,
                        "cat": rid,
                        "pid": data['pid'],
                        "tid": data['name'],
                        "ts": data['start_time']
                    }
                if data["name"] == "httpReq":
                    flow_event["ph"] = 's'
                elif data["name"] == "httpRes":
                    flow_event["ph"] = 'f'
                    flow_event["bp"] = 'e'
                else:
                    flow_event["ph"] = 't'
                trace_events.append(flow_event)
        if data['type'] == 1:
            trace_events.append(
                {
                    "name": data["name"],
                    "ph": "C",
                    "ts": data['start_time'],
                    "pid": data['pid'],
                    "tid": "NPU Usage",
                    "cat": "Metrics",
                    "args": {
                        'NPU Usage': data['message'].get('value', None)
                    }
                }
            )

    trace_events = add_cpu_events(cpu_data_df, trace_events)
    trace_events = sort_trace_events_by_cat(trace_events)

    trace_data = {"traceEvents": trace_events}
    return trace_data

def sort_trace_events_by_cat(trace_events):
    sorting_order = ['Metrics', 'Request Status', 'Execute']

    def get_sorting_key(event):
        if 'cat' in event and event["cat"] in sorting_order:
            return sorting_order.index(event['cat'])
        else:
            return float('inf')

    sort_events_by_cat = sorted(
        (event for event in trace_events if 'cat' in event),
        key=get_sorting_key
    )
    event_without_cat = [event for event in trace_events if 'cat' not in event]
    
    tid_sorting_order = ['deviceKvCache', 'hostKvCache', 'httpReq', 'httpRes', 'ReqEnQueue',
                         'ReqDeQueue', 'ReqState', 'BatchSchedule', 'modelExec']
    
    main_pid = 0
    for event_info in trace_events:
        if event_info.get("name") in tid_sorting_order:
            main_pid = event_info.get("pid")
            break
    tid_sorting_meta = [dict(
        name="thread_sort_index",
        ph="M",
        pid=main_pid,
        tid=tid,
        args=dict(sort_index=index)) for index, tid in enumerate(tid_sorting_order)]
        
    sorted_trace_events = sort_events_by_cat + event_without_cat + tid_sorting_meta
    return sorted_trace_events

def add_cpu_events(cpu_data_df, trace_events):
    for _, data in cpu_data_df.iterrows():
        trace_events.append(
            {
                "name": "CPU Usage",
                "ph": "C",
                "ts": data['start_time'],
                "pid": 1,
                "tid": "CPU Usage",
                "cat": "Metrics",
                "args": {
                    'CPU Usage': data['usage']
                }
            }
        )
    return trace_events

def add_args_for_state_type(message):
    args = {}
    name = message.get('name', None)
    if name == 'httpReq':
        args['recvTokenSize'] = message.get('recvTokenSize', None)
    if name == 'ReqEnQueue':
        args['queueID'] = message.get('queue', None)
        args['queueSize'] = message.get('size', None)
    if name == 'deviceKvCache':
        args['kvCacheValue'] = message.get('value', None)
        args['name'] = message.get('event', None)
    if name == 'hostKvCache':
        args['kvCacheValue'] = message.get('value', None)
        args['name'] = message.get('event', None)
    if name == 'ReqDeQueue':
        args['queueID'] = message.get('queue', None)
        args['queueSize'] = message.get('size', None)
    if name == 'httpRes':
        args['replyTokenSize'] = message.get('replyTokenSize', None)
    return args