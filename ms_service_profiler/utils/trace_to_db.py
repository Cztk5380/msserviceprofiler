# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import pandas as pd
import json
from collections import defaultdict
from ms_service_profiler.utils.log import logger
from ms_service_profiler.constant import NS_PER_US


DB_CACHE_SIZE = 1024

TRACE_TABLE_DEFINITIONS = {
    'process': """CREATE TABLE process 
        (pid TEXT PRIMARY KEY, process_name TEXT, label TEXT, process_sort_index INTEGER);""",
    'thread': """CREATE TABLE thread 
        (track_id INTEGER PRIMARY KEY, tid TEXT, pid TEXT, thread_name TEXT, thread_sort_index INTEGER);""",
    'slice': """CREATE TABLE slice 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, duration INTEGER, name TEXT, depth INTEGER, 
        track_id INTEGER, cat TEXT, args TEXT, cname TEXT, end_time INTEGER, flag_id TEXT);""",
    'counter': """CREATE TABLE counter 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, pid TEXT,timestamp INTEGER, cat TEXT, args TEXT);""",
    'flow': """CREATE TABLE flow 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id TEXT, name TEXT, cat TEXT, track_id INTEGER, 
        timestamp INTEGER, type TEXT);"""
}

UPDATE_PROCESS_NAME_SQL = """
    INSERT INTO  process (pid, process_name) VALUES (?, ?) ON CONFLICT (pid) 
    DO UPDATE SET process_name = excluded.process_name;
"""
UPDATE_THREAD_NAME_SQL = """
    INSERT INTO thread (track_id, tid, pid, thread_name) VALUES (?, ?, ?, ?) ON CONFLICT 
    (track_id) DO UPDATE SET tid = excluded.tid, pid = excluded.pid, thread_name = excluded.thread_name;
"""
UPDATE_PROCESS_LABLE_SQL = """
    INSERT INTO process (pid, label) VALUES (?, ?) ON CONFLICT (pid) DO UPDATE SET label = excluded.label;
"""
UPDATE_PROCESS_SORTINDEX_SQL = """
    INSERT INTO process (pid, process_sort_index) VALUES (?, ?) ON CONFLICT (pid) 
    DO UPDATE SET process_sort_index = excluded.process_sort_index;
"""
UPDATE_THREAD_SORTINDEX_SQL = """
    INSERT INTO thread (track_id, thread_sort_index) VALUES (?, ?) ON CONFLICT (track_id) 
    DO UPDATE SET thread_sort_index = excluded.thread_sort_index;
"""
SIMULATION_UPDATE_PROCESS_NAME_SQL = """
    INSERT INTO  process  (pid, process_name) VALUES (?, ?) ON CONFLICT (pid) 
    DO UPDATE SET process_name = CASE WHEN process_name IS NULL OR process_name = '' 
    THEN EXCLUDED.process_name ELSE process_name END;
"""
SIMULATION_UPDATE_THREAD_NAME_SQL = """
    INSERT INTO thread (track_id, tid, pid, thread_name, thread_sort_index) VALUES (?, ?, ?, ?, ?) 
    ON CONFLICT (track_id) DO UPDATE SET tid = CASE WHEN tid IS NULL OR tid = '' THEN EXCLUDED.tid ELSE tid END, 
    pid = CASE WHEN pid IS NULL OR pid = '' THEN EXCLUDED.pid ELSE pid END, thread_name = CASE WHEN thread_name IS NULL 
    OR thread_name = '' THEN EXCLUDED.thread_name ELSE thread_name END, thread_sort_index = CASE 
    WHEN thread_sort_index IS NULL OR thread_sort_index = 0 THEN EXCLUDED.thread_sort_index ELSE thread_sort_index END;
"""

UPDATA_SQL_TEMPLATES = {
    "slice": """INSERT INTO slice 
        (timestamp, duration, name, track_id, cat, args, cname, end_time, flag_id) 
        VALUES (:ts, :dur, :name, :track_id, :cat, :args, :cname, :end_time, :flag_id)""",
    "counter": """INSERT INTO counter 
        (name, pid, timestamp, cat, args) 
        VALUES (:name, :pid, :ts, :cat, :args)""",
    "flow": """INSERT INTO flow 
        (flow_id, name, track_id, timestamp, cat, type) 
        VALUES (:flow_id, :name, :track_id, :ts, :cat, :type)"""
}


def convert_ts_to_ns(ts):
    return float(ts) * NS_PER_US


# M: thread, process
def trans_trace_meta_data(event):
    args = event.get('args')
    args_name = args.get("name") if args is not None else ""
    args_label = args.get("labels") if args is not None else ""
    args_sort_index = args.get("sort_index") if args is not None else ""
    return {'name': event.get('name'), 'tid': event.get('tid'), 'pid': event.get('pid'), 'args_name': args_name,
        'args_label': args_label, 'args_sort_index': args_sort_index}


# X, I: slice
def trans_trace_slice_data(event):
    args = json.dumps(event.get('args'))
    ts = convert_ts_to_ns(event.get('ts'))
    dur = convert_ts_to_ns(event.get('dur'))
    return {'ts': ts, 'dur': dur, 'name': event.get('name'), 'pid': event.get('pid'),
        'tid': event.get('tid'), 'cat': event.get('cat'), 'args': args}


# s, f, t: flow
def trans_trace_flow_data(event):
    ts = convert_ts_to_ns(event.get('ts'))
    if event.get('name') == 'flow_0':
        print(ts)
    return {'ts': ts, 'name': event.get('name'), 'pid': event.get('pid'),
        'tid': event.get('tid'), 'cat': event.get('cat'), 'flow_id': event.get('id')}


# C: counter
def trans_trace_counter_data(event):
    id = event.get('id')
    name = event.get('name')
    args = json.dumps(event.get('args'))
    if id is not None:
        name = name + '[' + id + ']'
    ts = convert_ts_to_ns(event.get('ts'))
    return {'ts': ts, 'name': event.get('name'), 'pid': event.get('pid'),
        'tid': event.get('name'), 'cat': event.get('cat'), 'args': args}


class TrackIdManager:
    pid_tid_map = defaultdict(dict)
    current_max = 0

    @classmethod
    def get_track_id(cls, pid, tid):
        # 如果该pid tid组合已存在，则返回该track_id
        if tid in cls.pid_tid_map[pid]:
            return cls.pid_tid_map[pid][tid], True

        # 组合不存在，创建新的track_id
        new_id = cls.current_max
        cls.pid_tid_map[pid][tid] = new_id
        cls.current_max += 1
        return new_id, False


class ProcessTableManager:
    process_table = set()

    @classmethod
    def is_need_write_to_db(cls, pid, name):
        if (pid, name) not in cls.process_table:
            cls.process_table.add((pid, name))
            return False
        return True


class CacheTableManager:
    cache_list = {
        "slice": [],
        "counter": [],
        "flow": []
    }

    @classmethod
    def insert_cache_to_db(cls, data_type, cursor):
        cache_table = cls.cache_list[data_type]
        if len(cache_table) >= DB_CACHE_SIZE:
            cursor.executemany(
                UPDATA_SQL_TEMPLATES[data_type],
                cache_table
            )
            cache_table.clear()

    @classmethod
    def insert_all_cache_to_db(cls, cursor):
        for table_name, cache_table in cls.cache_list.items():
            if len(cache_table) >= 0:
                cursor.executemany(
                    UPDATA_SQL_TEMPLATES[table_name],
                    cache_table
                )
                cache_table.clear()


def trans_trace_meta_event(event, cursor):
    event_name = event.get('name')
    event_data = trans_trace_meta_data(event)
    pid = event_data.get('pid')

    if event_name == "process_name":
        cursor.execute(UPDATE_PROCESS_NAME_SQL, (pid, event_data.get('args_name')))
    elif event_name == "thread_name":
        tid = event_data.get('tid')
        track_id, _ = TrackIdManager.get_track_id(pid, tid)
        cursor.execute(UPDATE_THREAD_NAME_SQL, (track_id, tid, pid, event_data.get('args_name')))
    elif event_name == "process_labels":
        cursor.execute(UPDATE_PROCESS_LABLE_SQL, (pid, event_data.get('args_label')))
    elif event_name == "process_sort_index":
        cursor.execute(UPDATE_PROCESS_SORTINDEX_SQL, (pid, event_data.get('args_sort_index')))
    elif event_name == "thread_sort_index":
        tid = event_data.get('tid')
        track_id, _ = TrackIdManager.get_track_id(pid, tid)
        cursor.execute(UPDATE_THREAD_SORTINDEX_SQL, (track_id, event_data.get('args_sort_index')))
    else:
        logger.error(f'Trans trace M event to db failed due to event name {event_name}')


def write_to_process_thread_table(event_data, thread_sort_index, cursor):
    tid = event_data.get('tid')
    pid = event_data.get('pid')

    # 创建二级泳道
    if ProcessTableManager.is_need_write_to_db(pid, pid):
        cursor.execute(SIMULATION_UPDATE_PROCESS_NAME_SQL, (pid, pid))

    # 创建三级泳道
    track_id, exist = TrackIdManager.get_track_id(pid, tid)
    if not exist:
        cursor.execute(SIMULATION_UPDATE_THREAD_NAME_SQL, (track_id, tid, pid, tid, thread_sort_index))
    return track_id


def trans_trace_slice_event(event, cursor):
    event_data = trans_trace_slice_data(event)
    end_ts = event_data['ts'] + event_data['dur']

    track_id = write_to_process_thread_table(event_data, event.get('thread_sort_index'), cursor)

    # 创建slice块
    CacheTableManager.cache_list['slice'].append((event_data.get('ts'), event_data.get('dur'), event_data.get('name'),
        track_id, event.get('cat'), event_data.get('args'), event.get('cname'), end_ts, event.get('flag_id')))
    CacheTableManager.insert_cache_to_db('slice', cursor)


def trans_trace_counter_event(event, cursor):
    event_data = trans_trace_counter_data(event)
    if event_data.get('ts') == 0:
        return

    write_to_process_thread_table(event_data, event.get('thread_sort_index'), cursor)

    # 创建counter块
    CacheTableManager.cache_list['counter'].append((event_data.get('name'), event_data.get('pid'), event_data.get('ts'),
        event.get('cat'), event_data.get('args')))
    CacheTableManager.insert_cache_to_db('counter', cursor)


def trans_trace_flow_event(event, ph_type, cursor):
    event_data = trans_trace_flow_data(event)

    track_id = write_to_process_thread_table(event_data, event.get('thread_sort_index'), cursor)

    # 创建flow连线
    CacheTableManager.cache_list['flow'].append((event_data.get('flow_id'), event_data.get('name'), track_id,
        event_data.get('ts'), event_data.get('cat'), ph_type))
    CacheTableManager.insert_cache_to_db('flow', cursor)


def trans_trace_event(event, cursor):
    ph_type = event.get('ph')
    if ph_type == 'M':
        trans_trace_meta_event(event, cursor)
    if ph_type == 'X' or ph_type == 'I':
        trans_trace_slice_event(event, cursor)
    if ph_type == 'C':
        trans_trace_counter_event(event, cursor)
    if ph_type == 's' or ph_type == 't' or ph_type == 'f':
        trans_trace_flow_event(event, ph_type, cursor)


def save_cache_data_to_db(cursor):
    CacheTableManager.insert_all_cache_to_db(cursor)
