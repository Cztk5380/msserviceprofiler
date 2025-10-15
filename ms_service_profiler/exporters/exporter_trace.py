# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import json
import os
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
            logger.debug('Start write trace data to db')
            create_sqlite_tables(TRACE_TABLE_DEFINITIONS)
            save_trace_data_into_db(merged_data)
            logger.debug('Write trace data to db success')


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
        raise DatabaseError(f"Cannot update sqlite database when create trace table due to {ex}") from ex
    finally:
        if conn:
            conn.close()


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
    
    # 添加参数到DataFrame并转换为记录
    trace_event_df['args'] = args_list
    trace_events = trace_event_df[['name', 'ph', 'ts', 'dur', 'pid', 'tid', 'args']].to_dict(orient='records')
    
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
    if 'deviceBlock=' not in kv_data_df:
        return []
    kv_trace_df = kv_data_df.copy()

    # 优先使用 pid_label_map 中的 dp_rank
    if pid_label_map is not None and "pid" in kv_trace_df.columns:
        def get_name(row):
            pid = row['pid']
            # 优先使用 pid_label_map 中的 dp_rank
            if pid in pid_label_map and 'dp_rank' in pid_label_map[pid]:
                dp_rank = pid_label_map[pid]['dp_rank']
                return f"{row['domain']}-dp{dp_rank}"
            # 回退到 scope#dp
            elif "scope#dp" in kv_trace_df.columns:
                scope_dp = row["scope#dp"]
                if pd.notna(scope_dp):
                    return f"{row['domain']}-dp{int(scope_dp)}"
            # 都没有就只返回 domain
            return row['domain']

        kv_trace_df['name'] = kv_trace_df.apply(get_name, axis=1)
    elif "scope#dp" in kv_trace_df:
        # 没有 pid_label_map 时使用 scope#dp
        kv_trace_df['name'] = kv_trace_df['domain'] + '-dp' + kv_trace_df["scope#dp"].astype(int,
                                                                                             errors='ignore').astype(
            str)
    else:
        # 都没有就只返回 domain
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
