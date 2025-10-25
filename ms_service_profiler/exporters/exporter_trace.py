# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import time
import psutil
import math
import multiprocessing as mp
import json
from dataclasses import dataclass
from typing import Any, Optional
from multiprocessing import Queue, Process
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from ms_service_profiler.exporters.base import TaskExporterBase
from ms_service_profiler.utils.file_open_check import ms_open, safe_json_dump, OpenException
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import DatabaseError, key_except
from ms_service_profiler.exporters.utils import get_db_connection, create_sqlite_tables
from ms_service_profiler.utils.trace_to_db import (
    TRACE_TABLE_DEFINITIONS, trans_trace_meta_event,
    trans_trace_slice_data,  trans_trace_counter_data, trans_trace_flow_data,
    write_to_process_thread_table, reset_track_id_manager,
    reset_process_table_manager, clear_data_cache
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
        data, mspti = self.get_depends_result("pipeline:service", None), self.get_depends_result("pipeline:mspti", None)

        if self.task_index == 0 and (data is not None or mspti is not None):
            data_list = self.gather((None, None), dst=0)
        else:
            data_list = self.gather((data, mspti), dst=0)

        if data_list is None:
            return None

        if self.task_index == 0 and (data is not None or mspti is not None):
            data_list[0] = (data, mspti)

        # 使用列表推导式过滤并提取非None值
        all_data = [item[0] for item in data_list if item is not None and item[0] is not None]
        all_mspti = [item[1] for item in data_list if item is not None and item[1] is not None]

        # 获取第一个非None的值
        valid_data = all_data[0] if all_data else None
        valid_mspti = all_mspti[0] if all_mspti else None

        self.export(valid_data, valid_mspti)
        return None

    @classmethod
    @timer(logger.debug)
    def export(cls, data, mspti) -> None:
        if 'db' not in cls.args.format and 'json' not in cls.args.format:
            return

        output = cls.args.output_path

        if data is not None:
            all_data_df = data.get('tx_data_df', pd.DataFrame(columns=["name", "domain"])).copy()

            # 对domain进行预处理，以便相同domain的数据在同一个泳道中显示
            prepare_domain_for_process(all_data_df)

            if 'pid_label_map' in data:
                pid_label_map = data['pid_label_map']
            else:
                pid_label_map = None

            msprof_data_df = data.get('msprof_data', pd.DataFrame())

            cann_data = []
            pid_ppid_map = []
            for index, pf in enumerate(msprof_data_df):
                msprof_data_ppid = pf.get("pid")
                msprof_data_pids = set()
                for prof_path in pf.get("msprof_files"):
                    cann_prof_data, msprof_data_pids = load_single_prof(prof_path, index)
                    cann_data.append(cann_prof_data)
                for msprof_data_pid in msprof_data_pids:
                    pid_ppid_map.append((msprof_data_pid, msprof_data_ppid))
            
            if "ppid" in all_data_df and "pid" in all_data_df:
                pid_ppid_map.extend(set(zip(all_data_df['pid'], all_data_df['ppid'])))

            pid_ppid_map = [(str(pid), ppid, pid) for pid, ppid in pid_ppid_map]
            
            trace_data = create_trace_events(all_data_df, pid_label_map, pid_ppid_map)
            merged_data = merge_json_data(trace_data, cann_data)
        else:
            merged_data = {"traceEvents": []}

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


def prepare_domain_for_process(all_data_df):
    # 如果只采集到了python数据而没有采集到cpp数据，则直接认为name为domain，确保domain列存在
    if 'domain' not in all_data_df.columns:
        all_data_df['domain'] = all_data_df['name']  # 直接添加新列

    # 过滤显示数据, Meta不显示
    meta_mask = all_data_df['domain'].isin(['Meta'])
    all_data_df.drop(all_data_df[meta_mask].index, inplace=True)
    
    # 对于非Request, RequestState, KVCache泳道区分tid显示
    mask = ~all_data_df['domain'].isin(['Request', 'RequestState', 'KVCache'])
    all_data_df.loc[mask, 'domain'] = (
        all_data_df.loc[mask, 'domain'].astype(str) 
        + '(' 
        + all_data_df.loc[mask, 'tid'].astype(str)
        + ')'
    )

    all_data_df['domain'] = all_data_df['domain'].replace('PDSplit', 'PDCommunication')


def process_prof_trace_events(events, index):
    pid_list = set()
    for event in events:
        pid_list.add(event.get('pid'))
        event_id = event.get('id')
        event_ph = event.get('ph')
        if event_id is not None and event_ph in ['s', 'f']:
            # 将 event_id 和 index 转换为字符串并拼接，保证不会重复
            event['id'] = str(event_id) + '_' + str(index)

    pid_list.discard(None)
    return [x for x in events if x.get("name") != 'process_sort_index'], pid_list


def load_single_prof(pf, prof_id):
    try:
        with ms_open(pf, 'r', encoding='utf-8', max_size=-1) as file:
            trace_events = json.load(file)
    except OpenException as oe:
        logger.warning(f"cannot read file %r occurred {oe}", pf)
        return {"traceEvents": []}, set()
    except FileNotFoundError:
        logger.warning("The %r file was not found. Please check the file path.", pf)
        return {"traceEvents": []}, set()
    except json.JSONDecodeError:
        logger.warning(
            "%r is not in a valid JSON format, which might be normal.", pf
        )
        return {"traceEvents": []}, set()

    trace_events, pid_list = process_prof_trace_events(trace_events, prof_id)

    return {"traceEvents": trace_events}, pid_list


def find_cann_pid(trace_events):
    for event in trace_events:
        if event.get("name") == "process_name":
            args = event.get("args", {})
            if args.get("name") == "CANN":
                return event.get("pid")
    return None


def merge_json_data(trace_data, msprof_data_df):
    for item in msprof_data_df:
        events = item.get("traceEvents", [])
        trace_data["traceEvents"].extend(events)
    return trace_data


@timer(logger.debug)
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

    # 初始化 ph 列为默认值
    exploded_df['ph'] = 't'

    # 如果某个 rid 只有一行，根据during_time是否为0区分，为0就是ph=i，否则ph=x
    single_occurrences = exploded_df['rid'].value_counts()
    single_rids = single_occurrences[single_occurrences == 1].index
    single_mask = exploded_df['rid'].isin(single_rids)

    # 根据 during_time 的值来设置 ph（优先处理）
    during_time_zero_mask = exploded_df['during_time'] == 0
    exploded_df.loc[single_mask & during_time_zero_mask, 'ph'] = 'i'  # 瞬时事件
    exploded_df.loc[single_mask & ~during_time_zero_mask, 'ph'] = 'X'  # 完整事件

    # 找出每个 rid 的第一次和最后一次出现的位置（排除单次出现的）
    multi_mask = ~single_mask  # 多次出现的记录
    first_occurrences = exploded_df[multi_mask].groupby('rid').head(1).index
    last_occurrences = exploded_df[multi_mask].groupby('rid').tail(1).index

    # 设置第一次出现为 's'
    exploded_df.loc[first_occurrences, 'ph'] = 's'

    # 设置最后一次出现为 'f'
    exploded_df.loc[last_occurrences, 'ph'] = 'f'

    exploded_df['bp'] = ['b' if ph == 'f' else '' for ph in exploded_df['ph']]
    exploded_df['name'] = 'flow_' + exploded_df['rid']
    exploded_df['ts'] = exploded_df['start_time']
    exploded_df['id'] = exploded_df['rid']
    exploded_df['cat'] = exploded_df['rid']
    exploded_df['pid'] = exploded_df['pid']
    flow_trace_events = exploded_df[['name', 'ph', 'ts', 'id', 'cat', 'pid', 'tid']].to_dict(orient='records')
    return flow_trace_events


def create_trace_events(all_data_df, pid_label_map=None, pid_ppid_map=None):
    metric_event = ['npu', 'KVCache', 'PullKVCache']

    # name 非空
    name_notna_condition = all_data_df['name'].notna()

    # 非metric数据
    domain_not_in_metric_condition = ~all_data_df['domain'].isin(metric_event)

    # 筛选掉domain为expert_hot开头的数据，不写入trace图
    prefix_to_exclude = 'expert_hot'
    domain_not_startswith_condition = ~all_data_df['domain'].str.startswith(prefix_to_exclude)

    # 普通事件
    valid_name_df = all_data_df[
        name_notna_condition &
        domain_not_in_metric_condition &
        domain_not_startswith_condition
    ]
    trace_events = add_trace_events(valid_name_df)

    if not all_data_df.empty and "name" in all_data_df:
        npu_trace_events = add_npu_events(all_data_df[all_data_df['name'] == 'npu'])
        trace_events.extend(npu_trace_events)

        kv_trace_events = add_kvcache_events(all_data_df[all_data_df['domain'] == 'KVCache'], pid_label_map)
        trace_events.extend(kv_trace_events)

        pull_kvcache_events = add_pull_kvcache_events(all_data_df[all_data_df['domain'] == 'PullKVCache'])
        trace_events.extend(pull_kvcache_events)

        # flow事件
        flow_event_df = valid_name_df[valid_name_df['rid'].notna()]
        flow_trace_events = add_flow_event(flow_event_df)
        trace_events.extend(flow_trace_events)
        
    trace_events = sort_trace_events_by_tid(trace_events)

    coordinator_pid = None
    for event in trace_events:
        tid = event.get("tid", "")
        if isinstance(tid, str) and "Coordinator" in tid:
            coordinator_pid = event["pid"]
            break  # 找到第一个就退出


    if pid_label_map is not None or pid_ppid_map is not None:
        trace_events.extend(sort_trace_events_by_pid(pid_label_map, pid_ppid_map, coordinator_pid))

    trace_data = {"traceEvents": trace_events}
    return trace_data


def sort_trace_events_by_pid(pid_label_map, pid_ppid_map, coordinator_pid=None):
    pid_sorting_meta = []
    
    process_tree = {}
    for pid, ppid, _ in pid_ppid_map:
        process_tree[pid] = ppid
    
    process_prefix = {}
    
    def build_prcess_prefix(pid):
        if pid in process_prefix:
            return process_prefix[pid]
        ppid = process_tree.get(pid)
        if ppid is None:
            return ""
        
        ppid_prefix = build_prcess_prefix(ppid)
        pid_prefix = f"{ppid_prefix}.{pid}"
        process_prefix[pid] = pid_prefix
        return pid_prefix
    
    process_prefix_list = [(ori_pid, build_prcess_prefix(pid)) for pid, _, ori_pid in pid_ppid_map]
    
    process_prefix_list.sort(key=lambda x: x[1])

    def sort_key(item):
        pid, prefix = item
        return (0, "") if pid == coordinator_pid else (1, prefix)

    process_prefix_list.sort(key=sort_key)

    for index, item in enumerate(process_prefix_list):
        pid, _ = item
        pid_sorting_meta.append(dict(
            name="process_sort_index",
            ph="M",
            pid=pid,
            args=dict(sort_index=index))
        )
        labels = []
        if pid_label_map is not None and "host_name" in pid_label_map.get(pid, []): 
            labels.append(pid_label_map.get(pid).get("host_name"))
        if pid_label_map is not None and "dp" in pid_label_map.get(pid, []): 
            labels.append(f"dp{pid_label_map.get(pid).get('dp')}")
        elif pid_label_map is not None and "dp_rank" in pid_label_map.get(pid, []): 
            labels.append(f"dp{pid_label_map.get(pid).get('dp_rank')}")

        if labels:
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
    """将有效名称数据转换为跟踪事件列表"""
    # 添加基本跟踪事件字段
    trace_event_df = _add_basic_trace_fields(valid_name_df)
    
    # 确保所有必需的列都存在
    valid_name_df = _ensure_required_columns(valid_name_df)
    
    # 构建参数列表
    args_list = _build_args_list(valid_name_df)

    # 直接构建结果列表
    names = trace_event_df['name'].tolist()
    phs = trace_event_df['ph'].tolist()
    tss = trace_event_df['ts'].tolist()
    durs = trace_event_df['dur'].tolist()
    pids = trace_event_df['pid'].tolist()
    tids = trace_event_df['tid'].tolist()

    trace_events = [
        {
            'name': names[i],
            'ph': phs[i],
            'ts': tss[i],
            'dur': durs[i],
            'pid': pids[i],
            'tid': tids[i],
            'args': args_list[i]
        }
        for i in range(len(trace_event_df))
    ]

    return trace_events


def _add_basic_trace_fields(df):
    """添加基本跟踪事件字段到DataFrame"""
    trace_df = df.copy()
    trace_df['ph'] = ['I' if during_time == 0 else 'X' for during_time in df['during_time']]
    trace_df['ts'] = df['start_time']
    trace_df['tid'] = df['domain']
    trace_df['dur'] = df['during_time']
    return trace_df


def _ensure_required_columns(df):
    """确保DataFrame包含所有必需的列，缺失的列使用默认值填充"""
    required_columns = [
        'start_datetime', 'end_datetime', 'batch_type', 'batch_size',
        'res_list', 'rid', 'message', 'tid'
    ]

    column_defaults = {
        'start_datetime': pd.NaT,
        'end_datetime': pd.NaT,
        'batch_type': '',
        'batch_size': 0,
        'res_list': [],
        'rid': '',
        'message': {},
        'tid': 0
    }

    missing_columns = []
    for col in required_columns:
        if col not in df.columns:
            missing_columns.append(col)
            default_value = column_defaults.get(col, [])
            if default_value == []:
                df[col] = df.apply(lambda _: [], axis=1)
            else:
                df[col] = default_value

    if missing_columns:
        logger.warning(f"Missing columns in trace event data, using defaults: {missing_columns}")
    
    return df


def _build_args_list(df):
    """从DataFrame构建参数列表"""
    required_columns = [
        'start_datetime', 'end_datetime', 'batch_type', 'batch_size',
        'res_list', 'rid', 'message', 'tid'
    ]
    
    args_list = []
    try:
        selected_df = df[required_columns]

        for row in selected_df.itertuples(index=False, name='TraceRow'):
            args_dict = _process_row_to_args(row)
            args_list.append(args_dict)

    except Exception as e:
        logger.error(f"Error during trace event generation: {e}")
        return []
    
    return args_list


def _process_row_to_args(row):
    """处理单行数据并转换为参数字典"""
    start, end, batch_type, batch_size, res_list, rid, message, tid = row
    
    # 从message中排除特定键
    args_dict = {k: v for k, v in message.items() if k not in ["domain", "name", "type", "rid"]}
    
    # 添加基本字段
    args_dict.update({
        'start_datetime': start,
        'end_datetime': end,
        'tid': tid
    })
    
    # 条件添加可选字段
    if batch_size is not None and is_valid_value(batch_size):
        args_dict.update({'batch_size': batch_size})
        
    if batch_type is not None and is_valid_value(batch_type):
        args_dict.update({'batch_type': batch_type})
        
    if res_list is not None and is_valid_value(res_list):
        args_dict.update({"res_list": res_list})
        
    if batch_size is None and rid != res_list:
        args_dict.update({"rid": rid})
    
    return args_dict


def is_valid_value(x):
    """
    判断是否一个值是否非空、非Nan值等
    涉及到多种数据格式
    """
    if x is None:
        return False
    if isinstance(x, (list, tuple)) and len(x) == 0:
        return False
    if isinstance(x, str) and x.strip() == "":
        return False
    if isinstance(x, (list, tuple)):
        # 对于列表，检查是否全为 None/空/NaN
        return not all(item is None or (isinstance(item, str) and item.strip() == "") for item in x)
    if isinstance(x, (np.ndarray, pd.Series)):
        return len(x) > 0 and not pd.isna(x).all()
    # 其他情况：数字、非空字符串等都算有效
    return not pd.isna(x)


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


def add_kvcache_events(kv_data_df, pid_label_map=None):
    if 'deviceBlock=' not in kv_data_df.columns:
        return []

    # 预声明变量避免分支中重复检查
    has_pid_map = pid_label_map is not None and "pid" in kv_data_df.columns
    has_scope_dp = "scope#dp" in kv_data_df.columns

    # 向量化处理name列
    name = _build_name_column(kv_data_df, pid_label_map, has_pid_map, has_scope_dp)

    # 构建结果DataFrame
    result_df = pd.DataFrame({
        'name': name,
        'ph': 'C',
        'ts': kv_data_df['start_time'],
        'pid': kv_data_df['pid'] if 'pid' in kv_data_df else None,
        'tid': kv_data_df['domain'],
        'args': [{'Device Block': x} for x in kv_data_df['deviceBlock=']]
    })

    # 使用itertuples加速字典转换
    return [dict(name=r.name, ph=r.ph, ts=r.ts, pid=r.pid, tid=r.tid, args=r.args)
            for r in result_df.itertuples(index=False)]


def _build_name_column(kv_data_df, pid_label_map, has_pid_map, has_scope_dp):
    """构建name列的逻辑"""
    if has_pid_map:
        return _build_name_with_pid_map(kv_data_df, pid_label_map, has_scope_dp)
    elif has_scope_dp:
        return (kv_data_df['domain'] + '-dp' +
                kv_data_df['scope#dp'].astype(int, errors='ignore').astype(str))
    else:
        return kv_data_df['domain']


def _build_name_with_pid_map(kv_data_df, pid_label_map, has_scope_dp):
    """当有pid_map时构建name列"""
    # 构建pid到dp_rank的向量化映射
    dp_rank_map = {pid: info['dp_rank'] for pid, info in pid_label_map.items()
                   if 'dp_rank' in info}

    dp_ranks = kv_data_df['pid'].map(dp_rank_map)
    has_dp_rank = dp_ranks.notna()
    name = kv_data_df['domain'].copy()

    # 处理有dp_rank的情况
    if has_dp_rank.any():
        name.loc[has_dp_rank] = (kv_data_df.loc[has_dp_rank, 'domain'] + '-dp' +
                                 dp_ranks[has_dp_rank].astype(int).astype(str))

    # 处理scope#dp回退
    if has_scope_dp:
        scope_dp_mask = ~has_dp_rank & kv_data_df['scope#dp'].notna()
        if scope_dp_mask.any():
            name.loc[scope_dp_mask] = (kv_data_df.loc[scope_dp_mask, 'domain'] + '-dp' +
                                       kv_data_df.loc[scope_dp_mask, 'scope#dp'].astype(int).astype(str))
    return name


def add_pull_kvcache_events(df):
    if df is None or df.shape[0] == 0:
        return []
    df_all_device = df.copy()
    all_events = []

    for rank in df_all_device['rank'].unique():
        try:
            rank = int(rank)
        except Exception as e:
            logger.warning(f"Unexpected error processing rank {rank}: {str(e)}, skipping this rank")
            continue
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


# 优化一下，不行就上上一版

def save_trace_data_into_db(trace_data):
    """
    使用智能进程数设置的多进程优化方案 - 性能优化版
    """
    events = trace_data.get("traceEvents", [])
    total = len(events)
    if total == 0:
        logger.warning("no data to write")
        return

    start_time = time.time()
    logger.warning(f"=== SMART MULTI-PROCESS: PROCESSING {total} EVENTS ===")

    # 重置状态（复用b.py中的函数）
    reset_track_id_manager()
    reset_process_table_manager()
    clear_data_cache()

    # 第一步：单进程构建track_id映射
    logger.warning("=== STEP 1: BUILDING TRACK_ID MAPPING ===")
    track_id_map = _build_track_id_mapping_smart(events)

    # 第二步：智能多进程数据准备
    logger.warning("=== STEP 2: SMART MULTI-PROCESS DATA PREPARATION ===")
    other_events = [e for e in events if e.get('ph') != 'M']

    if other_events:
        data_results = _prepare_data_smart_parallel(other_events, track_id_map)
    else:
        data_results = {'slice': [], 'counter': [], 'flow': []}

    # 第三步：单进程批量写入
    logger.warning("=== STEP 3: BATCH WRITE ===")
    _write_all_data_smart(data_results)

    elapsed = time.time() - start_time
    logger.warning(f"✅ Smart multi-process completed in {elapsed:.3f}s")


def _build_track_id_mapping_smart(events):
    """
    优化的track_id映射构建 - 复用b.py中的函数
    """
    track_id_map = {}

    conn = get_db_connection()
    if not conn:
        logger.warning("❌ Failed to get database connection for track_id mapping")
        return track_id_map

    try:
        cursor = conn.cursor()
        _setup_database_optimizations(cursor)

        unique_pid_tid, meta_events = _collect_pid_tid_and_meta_events(events)
        _process_meta_events_batch(meta_events, cursor)
        _process_pid_tid_batch(events, unique_pid_tid, track_id_map, cursor)

        conn.commit()
        logger.warning(f"✅ Built track_id mapping with {len(track_id_map)} entries")

    except Exception as e:
        logger.warning(f"❌ Error during track_id mapping: {e}")
        conn.rollback()
    finally:
        conn.close()

    return track_id_map


def _setup_database_optimizations(cursor):
    """设置数据库优化参数"""
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA cache_size = 10000")
    cursor.execute("PRAGMA synchronous = NORMAL")


def _collect_pid_tid_and_meta_events(events):
    """收集所有需要的pid,tid对和meta事件"""
    unique_pid_tid = set()
    meta_events = []

    for event in events:
        ph_type = event.get('ph')
        if ph_type == 'M':
            meta_events.append(event)
        else:
            pid = event.get('pid')
            tid = _get_tid_from_event(event, ph_type)
            if pid is not None and tid is not None:
                unique_pid_tid.add((pid, tid))

    return unique_pid_tid, meta_events


def _get_tid_from_event(event, ph_type):
    """从事件中提取tid"""
    if ph_type == 'C':
        return event.get('name')
    return event.get('tid')


def _process_meta_events_batch(meta_events, cursor):
    """批量处理meta事件"""
    for event in meta_events:
        trans_trace_meta_event(event, cursor)


def _process_pid_tid_batch(events, unique_pid_tid, track_id_map, cursor):
    """批量处理pid,tid对"""
    for pid, tid in unique_pid_tid:
        thread_sort_index = _find_thread_sort_index(events, pid, tid)
        track_id = write_to_process_thread_table(
            {'pid': pid, 'tid': tid}, thread_sort_index, cursor
        )
        track_id_map[(pid, tid)] = track_id


def _find_thread_sort_index(events, pid, tid):
    """查找线程排序索引"""
    for event in events:
        if event.get('pid') == pid and event.get('tid') == tid:
            return event.get('thread_sort_index', 0)
    return 0


def _prepare_data_smart_parallel(events, track_id_map):
    """
    智能多进程数据准备 - 优化进程配置
    """
    total_events = len(events)
    if total_events == 0:
        return {'slice': [], 'counter': [], 'flow': []}

    # 优化的进程数和分块大小配置 - 针对大数据量
    if total_events > 5000000:  # 超过500万事件
        optimal_processes = min(mp.cpu_count() - 1, 8)  # 限制最大8个进程
        chunk_size = max(200000, total_events // optimal_processes)
    else:
        num_processes, chunk_size = _calculate_smart_process_config(total_events)
        optimal_processes = num_processes

    # 创建分块
    chunks = [events[i:i + chunk_size] for i in range(0, total_events, chunk_size)]

    logger.warning(f"Smart config: {len(chunks)} processes, {chunk_size} chunk size for {total_events} events")

    # 使用进程池处理
    with mp.Pool(processes=len(chunks),
                 initializer=_init_worker_shared,
                 initargs=(track_id_map,)) as pool:

        results = []
        completed = 0

        # 使用imap_unordered提高效率
        for result in pool.imap_unordered(_process_chunk_smart, chunks, chunksize=1):
            results.append(result)
            completed += 1

            # 进度报告
            if completed % 10 == 0 or completed == len(chunks):
                logger.warning(f"Processed {completed}/{len(chunks)} chunks")

    # 合并结果
    final_result = {'slice': [], 'counter': [], 'flow': []}
    for result in results:
        final_result['slice'].extend(result['slice'])
        final_result['counter'].extend(result['counter'])
        final_result['flow'].extend(result['flow'])

    logger.warning(f"Data preparation completed: {len(final_result['slice'])} slices, "
                   f"{len(final_result['counter'])} counters, {len(final_result['flow'])} flows")
    return final_result


def _calculate_smart_process_config(total_events):
    """
    智能计算进程数和分块大小配置
    """
    # 获取系统信息
    cpu_count = mp.cpu_count()
    memory_info = psutil.virtual_memory()
    total_memory_gb = memory_info.total / (1024 ** 3)
    available_memory_gb = memory_info.available / (1024 ** 3)

    logger.warning(f"System: {cpu_count} CPUs, {total_memory_gb:.1f}GB RAM, {available_memory_gb:.1f}GB available")

    # 基于CPU的进程数
    cpu_based = max(2, cpu_count - 1)  # 保留一个核心用于系统任务

    # 基于内存的进程数
    memory_per_process_mb = 200  # 保守估计每个进程200MB
    memory_based = int(available_memory_gb * 1024 / memory_per_process_mb * 0.7)  # 使用70%可用内存

    # 基于数据量的进程数
    target_events_per_process = 400000
    data_based = max(4, min(32, math.ceil(total_events / target_events_per_process)))

    # 计算最优进程数（取三者最小值）
    optimal_processes = min(cpu_based, memory_based, data_based)

    # 确保进程数在合理范围内
    optimal_processes = max(4, min(optimal_processes, 32))

    # 计算分块大小
    chunk_size = max(50000, math.ceil(total_events / optimal_processes))

    # 如果分块太大，增加进程数
    if chunk_size > 600000:
        additional_processes = math.ceil(chunk_size / 400000)
        optimal_processes = min(32, optimal_processes + additional_processes)
        chunk_size = math.ceil(total_events / optimal_processes)

    logger.warning(f"Process config: CPU={cpu_based}, Memory={memory_based}, Data={data_based}, "
                   f"Final={optimal_processes} processes, {chunk_size} chunk size")

    return optimal_processes, chunk_size


def _process_chunk_smart(events_chunk):
    """
    智能处理数据块 - 复用b.py中的转换函数

    Args:
        events_chunk: 事件数据块

    Returns:
        dict: 包含三种类型数据的字典
    """
    slice_data = []
    counter_data = []
    flow_data = []

    for event in events_chunk:
        _process_single_event(event, slice_data, counter_data, flow_data)

    return {
        'slice': slice_data,
        'counter': counter_data,
        'flow': flow_data
    }


def _process_single_event(event, slice_data, counter_data, flow_data):
    """处理单个事件"""
    try:
        ph_type = event.get('ph')

        if _is_slice_event(ph_type, event):
            data = _prepare_slice_data_smart(event)
            if data:
                slice_data.append(data)

        elif _is_counter_event(ph_type, event):
            data = _prepare_counter_data_smart(event)
            if data:
                counter_data.append(data)

        elif _is_flow_event(ph_type, event):
            data = _prepare_flow_data_smart(event, ph_type)
            if data:
                flow_data.append(data)

    except (ValueError, KeyError, TypeError) as e:
        logger.debug(f"处理事件时遇到数据异常: {e}, 事件: {event.get('name', 'unknown')}")

    except Exception as e:
        logger.error(f"处理事件时遇到意外错误: {e}, 事件: {event.get('name', 'unknown')}")


def _is_slice_event(ph_type, event):
    """判断是否为切片事件"""
    return ph_type in ('X', 'I') and event.get('ts') is not None and event.get('dur') is not None


def _is_counter_event(ph_type, event):
    """判断是否为计数器事件"""
    return ph_type == 'C' and event.get('ts') is not None


def _is_flow_event(ph_type, event):
    """判断是否为流事件"""
    return ph_type in ('s', 't', 'f') and event.get('ts') is not None


@dataclass
class SliceData:
    """切片数据的数据类"""
    timestamp: float
    duration: float
    name: str
    track_id: int
    category: Optional[str]
    args: Optional[dict]
    color_name: Optional[str]
    end_timestamp: float
    flag_id: Optional[int]


@dataclass
class CounterData:
    """计数器数据的数据类"""
    name: str
    process_id: int
    timestamp: float
    category: Optional[str]
    args: Optional[dict]


def _prepare_slice_data_smart(event: dict) -> Optional[SliceData]:
    """智能slice数据处理 - 复用b.py的转换函数

    Args:
        event: 原始事件数据

    Returns:
        Optional[SliceData]: 切片数据对象，如果track_id无效则返回None
    """
    # 复用b.py中的转换函数
    event_data = trans_trace_slice_data(event)

    pid = event.get('pid')
    tid = event.get('tid')
    track_id = _worker_track_id_map.get((pid, tid), 0)

    if track_id == 0:
        return None

    end_timestamp = event_data['ts'] + event_data['dur']

    return SliceData(
        timestamp=event_data.get('ts'),
        duration=event_data.get('dur'),
        name=event_data.get('name'),
        track_id=track_id,
        category=event.get('cat'),
        args=event_data.get('args'),
        color_name=event.get('cname'),
        end_timestamp=end_timestamp,
        flag_id=event.get('flag_id')
    )


def _prepare_counter_data_smart(event: dict) -> Optional[CounterData]:
    """智能counter数据处理 - 复用b.py的转换函数

    Args:
        event: 原始事件数据

    Returns:
        Optional[CounterData]: 计数器数据对象，如果时间戳为0则返回None
    """
    # 复用b.py中的转换函数
    event_data = trans_trace_counter_data(event)

    if event_data.get('ts') == 0:
        return None

    return CounterData(
        name=event_data.get('name'),
        process_id=event_data.get('pid'),
        timestamp=event_data.get('ts'),
        category=event.get('cat'),
        args=event_data.get('args')
    )


def _prepare_flow_data_smart(event, ph_type):
    """智能flow数据处理 - 复用b.py的转换函数"""
    # 复用b.py中的转换函数
    event_data = trans_trace_flow_data(event)

    pid = event.get('pid')
    tid = event.get('tid')

    track_id = _worker_track_id_map.get((pid, tid), 0)
    if track_id == 0:
        return None

    return (
        event_data.get('flow_id'), event_data.get('name'), track_id,
        event_data.get('ts'), event.get('cat'), ph_type
    )


def _write_all_data_smart(data_results):
    """
    智能批量写入数据 - 增大批次大小
    """
    conn = get_db_connection()
    if not conn:
        logger.warning("❌ Failed to get database connection for final write")
        return

    try:
        cursor = conn.cursor()

        # 数据库优化设置
        cursor.execute("PRAGMA journal_mode = WAL")  # 改回WAL模式，更稳定
        cursor.execute("PRAGMA cache_size = -100000")  # 增大缓存
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA temp_store = MEMORY")

        # 增大批次大小以提高性能
        batch_size = 100000  # 从50000增加到100000

        # 写入slice数据
        slice_data = data_results['slice']
        if slice_data:
            logger.warning(f"Writing {len(slice_data)} slice records")
            for i in range(0, len(slice_data), batch_size):
                batch = slice_data[i:i + batch_size]
                cursor.executemany("""
                    INSERT INTO slice (timestamp, duration, name, track_id, cat, args, cname, end_time, flag_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                if (i // batch_size) % 5 == 0:  # 调整进度报告频率
                    logger.warning(f"Written {min(i + batch_size, len(slice_data))}/{len(slice_data)} slice records")

        # 写入counter数据
        counter_data = data_results['counter']
        if counter_data:
            logger.warning(f"Writing {len(counter_data)} counter records")
            for i in range(0, len(counter_data), batch_size):
                batch = counter_data[i:i + batch_size]
                cursor.executemany("""
                    INSERT INTO counter (name, pid, timestamp, cat, args)
                    VALUES (?, ?, ?, ?, ?)
                """, batch)

        # 写入flow数据
        flow_data = data_results['flow']
        if flow_data:
            logger.warning(f"Writing {len(flow_data)} flow records")
            for i in range(0, len(flow_data), batch_size):
                batch = flow_data[i:i + batch_size]
                cursor.executemany("""
                    INSERT INTO flow (flow_id, name, track_id, timestamp, cat, type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, batch)

        conn.commit()
        total_written = len(slice_data) + len(counter_data) + len(flow_data)
        logger.warning(f"✅ Written {total_written} data records")

    except Exception as e:
        logger.warning(f"❌ Error during data writing: {e}")
        conn.rollback()
    finally:
        conn.close()


# 全局变量用于worker进程共享数据
_worker_track_id_map = None


def _init_worker_shared(track_id_map):
    """初始化worker进程，共享track_id映射"""
    global _worker_track_id_map
    _worker_track_id_map = track_id_map
