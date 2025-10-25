# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from decimal import Decimal
from collections import defaultdict
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.file_open_check import safe_json_dump
from ms_service_profiler.constant import NS_PER_US


DB_CACHE_SIZE = 10000

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
    return int((Decimal(str(ts)) * NS_PER_US))


# M类型: thread, process
def trans_trace_meta_data(event):
    args = event.get('args')
    args_name = args.get("name") if args is not None else ""
    args_label = args.get("labels") if args is not None else ""
    args_sort_index = args.get("sort_index") if args is not None else ""
    return {'name': event.get('name'), 'tid': event.get('tid'), 'pid': event.get('pid'), 'args_name': args_name,
        'args_label': args_label, 'args_sort_index': args_sort_index}


# X, I类型: slice
def trans_trace_slice_data(event):
    args = safe_json_dump(event.get('args'))
    ts = convert_ts_to_ns(event.get('ts'))
    dur = convert_ts_to_ns(event.get('dur'))
    return {'ts': ts, 'dur': dur, 'name': event.get('name'), 'pid': event.get('pid'),
        'tid': event.get('tid'), 'cat': event.get('cat'), 'args': args}


# s, f, t类型: flow
def trans_trace_flow_data(event):
    ts = convert_ts_to_ns(event.get('ts'))
    return {'ts': ts, 'name': event.get('name'), 'pid': event.get('pid'),
        'tid': event.get('tid'), 'cat': event.get('cat'), 'flow_id': event.get('id')}


# C类型: counter
def trans_trace_counter_data(event):
    cid = event.get('id')
    name = event.get('name')
    args = safe_json_dump(event.get('args'))
    if cid is not None:
        name = name + '[' + cid + ']'
    ts = convert_ts_to_ns(event.get('ts'))
    return {'ts': ts, 'name': event.get('name'), 'pid': event.get('pid'),
        'tid': event.get('name'), 'cat': event.get('cat'), 'args': args}


class TrackIdManager:
    pid_tid_map = defaultdict(dict)
    current_max = 1

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
    _local_cache = None

    @classmethod
    def get_cache(cls):
        if cls._local_cache is None:
            cls._local_cache = {
                "slice": [],
                "counter": [],
                "flow": []
            }
        return cls._local_cache

    @classmethod
    def insert_cache_to_db(cls, data_type, cursor, cache_size=None):
        if cache_size is None:
            cache_size = DB_CACHE_SIZE
        cache_table = cls.get_cache()[data_type]
        if len(cache_table) >= cache_size:
            cursor.executemany(
                UPDATA_SQL_TEMPLATES[data_type],
                cache_table
            )
            cache_table.clear()

    # 添加 cache_list 属性以兼容现有代码
    @classmethod
    @property
    def cache_list(cls):
        return cls.get_cache()


def trans_trace_meta_event(event, cursor):
    event_name = event.get('name')
    event_data = trans_trace_meta_data(event)
    pid = event_data.get('pid')
    tid = event_data.get('tid')

    if event_name == "process_name":
        cursor.execute(UPDATE_PROCESS_NAME_SQL, (pid, event_data.get('args_name')))
    elif event_name == "thread_name":
        # 对于thread_name事件，我们仍然需要创建线程记录
        track_id, _ = TrackIdManager.get_track_id(pid, tid)
        cursor.execute(UPDATE_THREAD_NAME_SQL, (track_id, tid, pid, event_data.get('args_name')))
    elif event_name == "process_labels":
        cursor.execute(UPDATE_PROCESS_LABLE_SQL, (pid, event_data.get('args_label')))
    elif event_name == "process_sort_index":
        cursor.execute(UPDATE_PROCESS_SORTINDEX_SQL, (pid, event_data.get('args_sort_index')))
    elif event_name == "thread_sort_index":
        # 关键修复：检查数据库中是否已存在该线程记录
        cursor.execute("SELECT track_id FROM thread WHERE pid = ? AND tid = ?", (pid, tid))
        result = cursor.fetchone()

        if result:
            # 如果记录已存在，更新排序索引
            track_id = result[0]
            cursor.execute(UPDATE_THREAD_SORTINDEX_SQL, (track_id, event_data.get('args_sort_index')))
        else:
            # 如果记录不存在，创建一个只有排序索引的空记录
            # 使用TrackIdManager获取track_id，但不创建完整的线程记录
            track_id, _ = TrackIdManager.get_track_id(pid, tid)
            cursor.execute(
                "INSERT INTO thread (track_id, thread_sort_index) VALUES (?, ?)",
                (track_id, event_data.get('args_sort_index'))
            )
            logger.warning(
                f"Created empty thread record with track_id={track_id}, sort_index={event_data.get('args_sort_index')}")
    else:
        logger.warning(f'Trans trace M event to db failed due to unknown event name {event_name}')


def write_to_process_thread_table(event_data, thread_sort_index, cursor):
    tid = event_data.get('tid')
    pid = event_data.get('pid')

    # 创建二级泳道
    if ProcessTableManager.is_need_write_to_db(pid, pid):
        cursor.execute(SIMULATION_UPDATE_PROCESS_NAME_SQL, (pid, pid))

    # 创建三级泳道
    track_id, exist = TrackIdManager.get_track_id(pid, tid)
    # logger.warning(f'three track-id is {track_id}, exist is {exist},pid is {pid}, tid is {tid}')
    if not exist:
        cursor.execute(SIMULATION_UPDATE_THREAD_NAME_SQL, (track_id, tid, pid, tid, thread_sort_index))
    return track_id


def trans_trace_slice_event(event, cursor):
    if event.get('ts') is None or event.get('dur') is None:
        return

    event_data = trans_trace_slice_data(event)
    end_ts = event_data['ts'] + event_data['dur']

    track_id = write_to_process_thread_table(event_data, event.get('thread_sort_index'), cursor)

    # 使用进程局部缓存
    CacheTableManager.get_cache()['slice'].append((
        event_data.get('ts'), event_data.get('dur'), event_data.get('name'),
        track_id, event.get('cat'), event_data.get('args'), event.get('cname'),
        end_ts, event.get('flag_id')
    ))
    CacheTableManager.insert_cache_to_db('slice', cursor, DB_CACHE_SIZE)


def trans_trace_counter_event(event, cursor):
    if event.get('ts') is None:
        return
    event_data = trans_trace_counter_data(event)
    if event_data.get('ts') == 0:
        return

    _ = write_to_process_thread_table(event_data, event.get('thread_sort_index'), cursor)

    # 使用进程局部缓存
    CacheTableManager.get_cache()['counter'].append((
        event_data.get('name'), event_data.get('pid'), event_data.get('ts'),
        event.get('cat'), event_data.get('args')
    ))
    CacheTableManager.insert_cache_to_db('counter', cursor, DB_CACHE_SIZE)


def trans_trace_flow_event(event, ph_type, cursor):
    if event.get('ts') is None:
        return
    event_data = trans_trace_flow_data(event)

    track_id = write_to_process_thread_table(event_data, event.get('thread_sort_index'), cursor)

    # 使用进程局部缓存
    CacheTableManager.get_cache()['flow'].append((
        event_data.get('flow_id'), event_data.get('name'), track_id,
        event_data.get('ts'), event_data.get('cat'), ph_type
    ))
    CacheTableManager.insert_cache_to_db('flow', cursor, DB_CACHE_SIZE)


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
    for data_type in CacheTableManager.get_cache().keys():
        CacheTableManager.insert_cache_to_db(data_type, cursor, 0)


def reset_track_id_manager():
    """重置TrackIdManager状态"""
    TrackIdManager.pid_tid_map.clear()
    TrackIdManager.current_max = 1
    logger.warning("TrackIdManager reset")


def reset_process_table_manager():
    """重置ProcessTableManager状态"""
    ProcessTableManager.process_table.clear()
    logger.warning("ProcessTableManager reset")


def clear_data_cache():
    """清空数据缓存"""
    CacheTableManager.cache_list['slice'].clear()
    CacheTableManager.cache_list['counter'].clear()
    CacheTableManager.cache_list['flow'].clear()
    logger.warning("Data cache cleared")
