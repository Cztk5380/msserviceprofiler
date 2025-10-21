# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import time
import multiprocessing as mp
import json
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
    save_cache_data_to_db, TRACE_TABLE_DEFINITIONS, trans_trace_event,
    CacheTableManager, UPDATA_SQL_TEMPLATES, DB_CACHE_SIZE
)
from ms_service_profiler.utils.trace_to_db import (
trans_trace_slice_event,
trans_trace_counter_event,
trans_trace_flow_event,
trans_trace_meta_event,
TrackIdManager,
SIMULATION_UPDATE_PROCESS_NAME_SQL,
ProcessTableManager,
write_to_process_thread_table,
trans_trace_flow_data,
SIMULATION_UPDATE_THREAD_NAME_SQL,
trans_trace_counter_data,
trans_trace_slice_data,
reset_track_id_manager,
reset_process_table_manager
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

        # if 'db' in cls.args.format:
        #     logger.info('Start write trace data to db')
        #     create_sqlite_tables(TRACE_TABLE_DEFINITIONS)
        #     start_time = time.time()
        #     # 存入db文件
        #     save_trace_data_into_db(merged_data)
        #     end_time = time.time()
        #     logger.warning(f'db write time is {end_time - start_time}')
        #     logger.info('Write trace data to db success')

        if 'db' in cls.args.format:
            logger.warning('Start write trace data to db')
            create_sqlite_tables(TRACE_TABLE_DEFINITIONS)

            # 前置检查：验证输入数据
            events = merged_data.get("traceEvents", [])
            meta_events = [e for e in events if e.get('ph') == 'M']
            logger.warning(f"Input data contains {len(events)} total events, including {len(meta_events)} meta events")

            if meta_events:
                # 显示元事件样本
                for i, event in enumerate(meta_events[:3]):
                    logger.warning(f"Sample meta event {i}: name='{event.get('name')}', pid={event.get('pid')}")

            start_time = time.time()
            save_trace_data_into_db(merged_data)
            end_time = time.time()
            logger.warning(f'db write time is {end_time - start_time}')
            logger.warning('Write trace data to db success')


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


# TODO:旧版代码，能跑但是丢数据
# def _process_event_direct(event):
#     """
#     Producer task: process single event and return results
#     """
#     try:
#
#         # Each process uses independent in-memory database
#         mem_conn = sqlite3.connect(":memory:")
#         mem_cursor = mem_conn.cursor()
#
#         # Create same table structure in memory database
#         for table_name, create_sql in TRACE_TABLE_DEFINITIONS.items():
#             mem_cursor.execute(create_sql)
#         mem_conn.commit()
#
#         # Process event
#         trans_trace_event(event, mem_cursor)
#
#         # Get data from CacheTableManager
#         results = []
#         cache_data = CacheTableManager.get_cache()
#         for data_type, rows in cache_data.items():
#             if rows:
#                 results.extend([(data_type, row) for row in rows])
#                 # Clear current process cache
#                 cache_data[data_type].clear()
#
#         mem_conn.close()
#         return results
#
#     except Exception as e:
#         logger.warning(f"Failed to process event: {str(e)}, event: {event.get('name', 'unknown')}")
#         return []
#
#
# def producer_worker(events_chunk, output_queue, batch_size=1000):
#     """
#     Producer process: process event chunk and put results into output queue
#     """
#     try:
#         logger.debug(f"Producer started processing {len(events_chunk)} events")
#         processed_count = 0
#         batch_results = []  # 批量收集结果
#
#         for event in events_chunk:
#             try:
#                 processed = _process_event_direct(event)
#                 if processed:
#                     batch_results.extend(processed)
#                     processed_count += len(processed)
#
#                     # 批量发送，减少队列操作
#                     if len(batch_results) >= batch_size:
#                         output_queue.put(batch_results)
#                         batch_results = []
#
#             except Exception as e:
#                 logger.debug(f"Failed to process event: {e}")
#                 continue
#
#         # 发送剩余结果
#         if batch_results:
#             output_queue.put(batch_results)
#
#         logger.debug(
#             f"Producer completed, processed {len(events_chunk)} events, generated {processed_count} data records")
#
#     except Exception as e:
#         logger.error(f"Producer process error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#
#
# def consumer_worker(input_queue, total_events):
#     """
#     Consumer process: get data from queue and batch write to database
#     """
#     try:
#         logger.debug("Consumer process started")
#         conn = get_db_connection()
#         if conn is None:
#             logger.error("Consumer failed to get database connection")
#             return
#
#         # 优化数据库设置
#         cursor = conn.cursor()
#
#         cursor.execute("PRAGMA journal_mode = WAL")
#         cursor.execute("PRAGMA cache_size = 10000")  # 增大缓存
#         cursor.execute("PRAGMA temp_store = MEMORY")  # 临时表用内存
#
#         cache = {}  # {data_type: list of rows}
#         total_processed = 0
#         batch_count = 0
#         last_log_time = time.time()
#
#         while True:
#             try:
#                 # 设置超时，避免永久阻塞
#                 item = input_queue.get(timeout=30)
#                 if item is None:  # 结束信号
#                     logger.debug("Received end signal")
#                     break
#
#                 batch_count += 1
#
#                 # 处理批量数据
#                 for data_type, row in item:
#                     if data_type not in cache:
#                         cache[data_type] = []
#                     cache[data_type].append(row)
#                     total_processed += 1
#
#                     # 批量写入
#                     if len(cache[data_type]) >= DB_CACHE_SIZE:
#                         if data_type in UPDATA_SQL_TEMPLATES:
#                             cursor.executemany(UPDATA_SQL_TEMPLATES[data_type], cache[data_type])
#                             cache[data_type].clear()
#
#                 # 减少提交频率，改为基于时间或数据量
#                 current_time = time.time()
#                 if current_time - last_log_time > 5:  # 每5秒提交一次
#                     conn.commit()
#                     logger.debug(f"Consumer processed {total_processed}/{total_events} data")
#                     last_log_time = current_time
#
#             except mp.queues.Empty:
#                 logger.warning("Queue timeout, continue waiting...")
#                 continue
#             except Exception as e:
#                 logger.error(f"Failed to process queue data: {e}")
#                 break
#
#         # 写入剩余数据
#         logger.debug("Start writing remaining cache data")
#         for data_type, rows in cache.items():
#             if rows and data_type in UPDATA_SQL_TEMPLATES:
#                 cursor.executemany(UPDATA_SQL_TEMPLATES[data_type], rows)
#                 logger.debug(f"Written remaining {data_type} data: {len(rows)}")
#
#         # 保存缓存数据
#         save_cache_data_to_db(cursor)
#
#         conn.commit()
#         conn.close()
#         logger.debug(f"Consumer process ended, total processed data: {total_processed}")
#
#     except Exception as e:
#         logger.error(f"Consumer process error: {str(e)}")
#         import traceback
#         logger.error(traceback.format_exc())
#
#
# def save_trace_data_into_db(trace_data):
#     """
#     Complete multi-process version: clear Producer and Consumer architecture
#     """
#     events = trace_data.get("traceEvents", [])
#     total = len(events)
#     if total == 0:
#         logger.warning("no data to write")
#         return
#
#     start_time = time.perf_counter()
#     logger.debug(f"Multi-process started processing {total} events")
#
#     # 根据数据量动态调整进程数
#     cpu_count = mp.cpu_count()
#
#     # 小数据量使用更少的进程
#     if total < 10000:
#         producer_processes = min(2, cpu_count)
#     elif total < 100000:
#         producer_processes = min(4, cpu_count)
#     else:
#         producer_processes = max(1, cpu_count - 1)
#
#     # 使用多进程队列
#     mp_queue = Queue(maxsize=1000)
#
#     # 分块
#     chunk_size = max(1, total // producer_processes)
#     chunks = [events[i:i + chunk_size] for i in range(0, total, chunk_size)]
#
#     logger.debug(f"Using {producer_processes} Producer processes, chunk size: {chunk_size}, chunk count: {len(chunks)}")
#
#     # 启动 Consumer 进程
#     consumer_process = Process(
#         target=consumer_worker,
#         args=(mp_queue, total)
#     )
#     consumer_process.start()
#     logger.debug("Consumer process started")
#
#     # 启动 Producer 进程
#     producer_processes_list = []
#     for i, chunk in enumerate(chunks):
#         process = Process(
#             target=producer_worker,
#             args=(chunk, mp_queue, chunk_size // 10)  # 动态调整批处理大小
#         )
#         process.start()
#         producer_processes_list.append(process)
#         logger.debug(f"Started Producer process {i + 1}/{len(chunks)}")
#
#     # 等待所有 Producer 进程完成
#     logger.debug("Waiting for all Producer processes to complete...")
#     for i, process in enumerate(producer_processes_list):
#         process.join()
#         logger.debug(f"Producer process {i + 1} completed")
#
#     # 发送结束信号给 Consumer
#     mp_queue.put(None)
#     logger.debug("Sent end signal to Consumer")
#
#     # 等待 Consumer 进程完成
#     consumer_process.join(timeout=60)
#     if consumer_process.is_alive():
#         logger.debug("Consumer process did not end within timeout")
#         consumer_process.terminate()
#     else:
#         logger.debug("Consumer process ended")
#
#     elapsed = time.perf_counter() - start_time
#     logger.debug(
#         f"✅ process down ，total_num: {total}, "
#         f"Producer num: {producer_processes}, "
#         f"time: {elapsed:.3f}s, "
#         f"speed: {total / elapsed:.2f} records/second")
#


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
    if has_pid_map:
        # 构建pid到dp_rank的向量化映射
        dp_rank_map = {}
        for pid, info in pid_label_map.items():
            if 'dp_rank' in info:
                dp_rank_map[pid] = info['dp_rank']

        # 使用map高效处理
        dp_ranks = kv_data_df['pid'].map(dp_rank_map)
        has_dp_rank = dp_ranks.notna()

        # 初始化name为domain (默认值)
        name = kv_data_df['domain'].copy()

        # 处理有dp_rank的情况
        if has_dp_rank.any():
            name.loc[has_dp_rank] = (
                    kv_data_df.loc[has_dp_rank, 'domain'] +
                    '-dp' +
                    dp_ranks[has_dp_rank].astype(int).astype(str)
            )

        # 处理scope#dp回退
        if has_scope_dp:
            scope_dp_mask = ~has_dp_rank & kv_data_df['scope#dp'].notna()
            if scope_dp_mask.any():
                name.loc[scope_dp_mask] = (
                        kv_data_df.loc[scope_dp_mask, 'domain'] +
                        '-dp' +
                        kv_data_df.loc[scope_dp_mask, 'scope#dp'].astype(int).astype(str)
                )
    elif has_scope_dp:
        # 无pid_map时处理scope#dp
        name = (
                kv_data_df['domain'] +
                '-dp' +
                kv_data_df['scope#dp'].astype(int, errors='ignore').astype(str)
        )
    else:
        name = kv_data_df['domain']

    # 避免完整复制DataFrame，只构建结果所需列
    result_df = pd.DataFrame({
        'name': name,
        'ph': 'C',
        'ts': kv_data_df['start_time'],
        'pid': kv_data_df['pid'] if 'pid' in kv_data_df else None,
        'tid': kv_data_df['domain'],
        'args': [{'Device Block': x} for x in kv_data_df['deviceBlock=']]
    })

    # 使用itertuples加速字典转换
    return [
        {
            'name': r.name,
            'ph': r.ph,
            'ts': r.ts,
            'pid': r.pid,
            'tid': r.tid,
            'args': r.args
        }
        for r in result_df.itertuples(index=False)
    ]


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

# # TODO:千万别删！！！！！！！！！！
# #  最新调试(能跑，但是缺了个Request的泳道，性能55s，不上不下)
#
#
# def save_trace_data_into_db(trace_data):
#     """
#     高性能版本：使用单进程批量写入策略，避免锁问题
#     """
#     events = trace_data.get("traceEvents", [])
#     total = len(events)
#     if total == 0:
#         logger.warning("no data to write")
#         return
#
#     start_time = time.time()
#
#     logger.warning(f"=== START PROCESSING ===")
#     logger.warning(f"Total events: {total}")
#
#     # 重置状态确保一致性
#     reset_track_id_manager()
#     reset_process_table_manager()
#     cache = CacheTableManager.get_cache()
#     cache['slice'].clear()
#     cache['counter'].clear()
#     cache['flow'].clear()
#
#     # 单进程批量处理：结合了记录创建和数据插入
#     logger.warning("=== PROCESSING ALL EVENTS IN SINGLE PROCESS ===")
#     conn = get_db_connection()
#     if not conn:
#         logger.warning("❌ Failed to get database connection")
#         return
#
#     try:
#         cursor = conn.cursor()
#
#         # 应用数据库优化设置
#         cursor.execute("PRAGMA journal_mode = WAL")
#         cursor.execute("PRAGMA cache_size = 10000")
#         cursor.execute("PRAGMA synchronous = NORMAL")  # 降低同步级别提高性能
#         cursor.execute("PRAGMA temp_store = MEMORY")
#
#         # 批量处理所有事件
#         records_processed = 0
#         data_records_processed = 0
#
#         # 先处理所有元事件
#         meta_events = [e for e in events if e.get('ph') == 'M']
#         logger.warning(f"Processing {len(meta_events)} meta events first")
#         for i, event in enumerate(meta_events):
#             try:
#                 trans_trace_meta_event(event, cursor)
#                 records_processed += 1
#             except Exception as e:
#                 logger.warning(f"Failed to process meta event: {e}")
#
#         # 然后批量处理其他事件
#         other_events = [e for e in events if e.get('ph') != 'M']
#         logger.warning(f"Processing {len(other_events)} other events")
#
#         batch_size = 10000
#         for i, event in enumerate(other_events):
#             try:
#                 # 使用旧版逻辑处理事件（包括记录创建和数据插入）
#                 trans_trace_event(event, cursor)
#                 records_processed += 1
#                 data_records_processed += 1
#
#                 # 定期提交和清空缓存
#                 if i % batch_size == 0 and i > 0:
#                     # 先保存缓存数据
#                     save_cache_data_to_db(cursor)
#                     # 提交事务
#                     conn.commit()
#                     logger.warning(f"Processed {i}/{len(other_events)} events, committed transaction")
#
#             except Exception as e:
#                 logger.warning(f"Failed to process event: {e}")
#                 continue
#
#         # 保存所有剩余的缓存数据
#         save_cache_data_to_db(cursor)
#
#         # 最终提交
#         conn.commit()
#         logger.warning(f"✅ Processed {records_processed} total events, {data_records_processed} data events")
#
#     except Exception as e:
#         logger.warning(f"❌ Error during processing: {e}")
#         conn.rollback()
#     finally:
#         conn.close()
#
#     elapsed = time.time() - start_time
#     logger.warning(
#         f"✅ Overall processing completed: "
#         f"Total events: {total}, "
#         f"Time: {elapsed:.3f}s")
#
#     # 验证数据一致性
#     verify_final_data_in_db()
#
#
# def verify_final_data_in_db():
#     """
#     验证数据库中的数据与预期一致
#     """
#     conn = get_db_connection()
#     if conn:
#         cursor = conn.cursor()
#
#         # 预期的记录数量（根据你的测试数据调整）
#         expected_counts = {
#             'process': 3,
#             'thread': 19,
#             'slice': 838740,
#             'counter': 171361,
#             'flow': 856805
#         }
#
#         actual_counts = {}
#         for table in expected_counts.keys():
#             cursor.execute(f"SELECT COUNT(*) FROM {table}")
#             actual_counts[table] = cursor.fetchone()[0]
#
#         logger.warning(f"=== FINAL RECORD COUNTS ===")
#         all_correct = True
#         for table, expected in expected_counts.items():
#             actual = actual_counts[table]
#             if actual == expected:
#                 logger.warning(f"✅ {table}: {actual} (correct)")
#             else:
#                 logger.warning(f"❌ {table}: {actual} (expected {expected})")
#                 all_correct = False
#
#         if all_correct:
#             logger.warning("🎉 All table counts are correct!")
#         else:
#             logger.warning("⚠️ Some table counts are incorrect")
#
#         conn.close()
#         return all_correct

# end



# 尝试修复request缺失的问题
def save_trace_data_into_db(trace_data):
    """
    修复版本：正确处理ph=M事件，不创建多余的线程记录
    """
    events = trace_data.get("traceEvents", [])
    total = len(events)
    if total == 0:
        logger.warning("no data to write")
        return

    start_time = time.time()
    logger.warning(f"=== PROCESSING {total} EVENTS ===")

    # 重置状态确保一致性
    reset_track_id_manager()
    reset_process_table_manager()
    cache = CacheTableManager.get_cache()
    cache['slice'].clear()
    cache['counter'].clear()
    cache['flow'].clear()

    # 单进程处理 - 使用修复的逻辑
    conn = get_db_connection()
    if not conn:
        logger.warning("❌ Failed to get database connection")
        return

    try:
        cursor = conn.cursor()

        # 优化数据库设置
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA cache_size = 10000")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA temp_store = MEMORY")

        # 处理所有事件
        processed_count = 0
        batch_size = 50000

        for i, event in enumerate(events):
            try:
                # 使用修复的逻辑处理事件
                trans_trace_event(event, cursor)
                processed_count += 1

                # 定期提交
                if i % batch_size == 0 and i > 0:
                    save_cache_data_to_db(cursor)
                    conn.commit()
                    logger.warning(f"Processed {i}/{total} events")

            except Exception as e:
                logger.warning(f"Failed to process event {i}: {e}")
                continue

        # 保存剩余数据并提交
        save_cache_data_to_db(cursor)
        conn.commit()
        logger.warning(f"✅ Processed {processed_count}/{total} events")

    except Exception as e:
        logger.warning(f"❌ Error during processing: {e}")
        conn.rollback()
    finally:
        conn.close()

    elapsed = time.time() - start_time
    logger.warning(f"✅ Processing completed in {elapsed:.3f}s")

    # 验证数据一致性
    verify_final_data_in_db()


def verify_final_data_in_db():
    """
    验证数据库中的数据与预期一致
    """
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()

        expected_counts = {
            'process': 3,
            'thread': 19,
            'slice': 838740,
            'counter': 171361,
            'flow': 856805
        }

        actual_counts = {}
        for table in expected_counts.keys():
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            actual_counts[table] = cursor.fetchone()[0]

        logger.warning(f"=== FINAL RECORD COUNTS ===")
        all_correct = True
        for table, expected in expected_counts.items():
            actual = actual_counts[table]
            if actual == expected:
                logger.warning(f"✅ {table}: {actual} (correct)")
            else:
                logger.warning(f"❌ {table}: {actual} (expected {expected})")
                all_correct = False

        # 特别检查thread表的内容
        cursor.execute("SELECT track_id, tid, pid, thread_name, thread_sort_index FROM thread ORDER BY track_id")
        threads = cursor.fetchall()
        logger.warning("=== THREAD TABLE CONTENTS ===")
        for thread in threads:
            logger.warning(
                f"track_id={thread[0]}, tid={thread[1]}, pid={thread[2]}, name={thread[3]}, sort_index={thread[4]}")

        if all_correct:
            logger.warning("🎉 All table counts are correct!")
        else:
            logger.warning("⚠️ Some table counts are incorrect")

        conn.close()
        return all_correct

