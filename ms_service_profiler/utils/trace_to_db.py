# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import math
import multiprocessing as mp
from decimal import Decimal
from collections import defaultdict
import psutil
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.file_open_check import safe_json_dump
from ms_service_profiler.exporters.utils import get_db_connection
from ms_service_profiler.constant import NS_PER_US


DB_CACHE_SIZE = 10000

# 进程配置常量
MIN_PROCESSES = 4                    # 最小进程数，确保有足够的并行度
MAX_PROCESSES = 32                   # 最大进程数限制，避免创建过多进程导致资源竞争
RESERVED_CPUS = 1                    # 保留的CPU核心数，用于系统任务和其他应用
MIN_SAFE_PROCESSES = 2               # 基于CPU计算时的最小安全进程数

# 内存配置常量
MEMORY_PER_PROCESS_MB = 200          # 每个进程预估内存占用（MB），基于实际测试和监控
MEMORY_USAGE_RATIO = 0.7             # 可用内存使用比例，保留30%内存给系统和其他应用

# 数据量配置常量
TARGET_EVENTS_PER_PROCESS = 400000   # 每个进程理想处理的事件数量，基于性能测试得出
MIN_CHUNK_SIZE = 50000               # 最小分块大小，确保每个进程有足够的工作量
LARGE_CHUNK_THRESHOLD = 600000       # 大分块阈值，超过此值需要增加进程数
CHUNK_SIZE_BASELINE = 400000         # 分块大小基准，用于计算需要增加的进程数
DEFAULT_BATCH_SIZE = 100000  # 默认批次大小，平衡性能与内存使用
PROGRESS_REPORT_FREQUENCY = 5  # 进度报告频率，每5个批次报告一次进度
MIN_BATCH_SIZE = 10000  # 最小批次大小，确保基本的批量写入效率
MAX_BATCH_SIZE = 200000  # 最大批次大小，防止内存溢出


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
    ON CONFLICT (track_id) DO UPDATE SET 
        tid = CASE WHEN tid IS NULL OR tid = '' OR tid = 'None' THEN EXCLUDED.tid ELSE tid END, 
        pid = CASE WHEN pid IS NULL OR pid = '' THEN EXCLUDED.pid ELSE pid END, 
        thread_name = CASE WHEN thread_name IS NULL OR thread_name = '' OR thread_name = 'None' THEN EXCLUDED.thread_name ELSE thread_name END, 
        thread_sort_index = CASE WHEN thread_sort_index IS NULL OR thread_sort_index = 0 THEN EXCLUDED.thread_sort_index ELSE thread_sort_index END;
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

SELECT_TID_SQL = "SELECT track_id FROM thread WHERE pid = ? AND tid = ?"
INSERT_THREAD_SQL = "INSERT INTO thread (track_id, thread_sort_index) VALUES (?, ?)"
INSERT_SLICE_SQL = """
            INSERT INTO slice (timestamp, duration, name, track_id, cat, args, cname, end_time, flag_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
INSERT_COUNTER_SQL = """
            INSERT INTO counter (name, pid, timestamp, cat, args)
            VALUES (?, ?, ?, ?, ?)
        """
INSERT_FLOW_SQL = """
            INSERT INTO flow (flow_id, name, track_id, timestamp, cat, type)
            VALUES (?, ?, ?, ?, ?, ?)
        """


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
            return True
        return False


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
        # 检查数据库中是否已存在该线程记录
        cursor.execute(SELECT_TID_SQL, (pid, tid))
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
                INSERT_THREAD_SQL,
                (track_id, event_data.get('args_sort_index'))
            )
            logger.debug(
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
    track_id, _ = TrackIdManager.get_track_id(pid, tid)

    # 通过Sql保证不会重复插入数据，但是要更新预插入的数据条目
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
    logger.debug("TrackIdManager reset")


def reset_process_table_manager():
    """重置ProcessTableManager状态"""
    ProcessTableManager.process_table.clear()
    logger.debug("ProcessTableManager reset")


def clear_data_cache():
    """清空数据缓存"""
    cache = CacheTableManager.get_cache()
    cache['slice'].clear()
    cache['counter'].clear()
    cache['flow'].clear()
    logger.debug("Data cache cleared")


def calculate_smart_process_config(total_events):
    """
    智能计算进程数和分块大小配置
    """
    # 获取系统信息
    cpu_count = mp.cpu_count()
    memory_info = psutil.virtual_memory()
    total_memory_gb = memory_info.total / (1024 ** 3)
    available_memory_gb = memory_info.available / (1024 ** 3)

    logger.debug(f"System: {cpu_count} CPUs, {total_memory_gb:.1f}GB RAM, {available_memory_gb:.1f}GB available")

    # 基于CPU的进程数
    cpu_based = max(MIN_SAFE_PROCESSES, cpu_count - RESERVED_CPUS)  # 保留一个核心用于系统任务

    # 基于内存的进程数
    memory_based = int(available_memory_gb * 1024 / MEMORY_PER_PROCESS_MB * MEMORY_USAGE_RATIO)  # 使用70%可用内存

    # 基于数据量的进程数
    data_based = max(MIN_PROCESSES, min(MAX_PROCESSES, math.ceil(total_events / TARGET_EVENTS_PER_PROCESS)))

    # 计算最优进程数（取三者最小值）
    optimal_processes = min(cpu_based, memory_based, data_based)

    # 确保进程数在合理范围内
    optimal_processes = max(MIN_PROCESSES, min(optimal_processes, MAX_PROCESSES))

    # 计算分块大小
    chunk_size = max(MIN_CHUNK_SIZE, math.ceil(total_events / optimal_processes))

    # 如果分块太大，增加进程数
    if chunk_size > LARGE_CHUNK_THRESHOLD:
        additional_processes = math.ceil(chunk_size / CHUNK_SIZE_BASELINE)
        optimal_processes = min(MAX_PROCESSES, optimal_processes + additional_processes)
        chunk_size = math.ceil(total_events / optimal_processes)

    logger.debug(f"Process config: CPU={cpu_based}, Memory={memory_based}, Data={data_based}, "
                   f"Final={optimal_processes} processes, {chunk_size} chunk size")

    return optimal_processes, chunk_size


def write_all_data_smart(data_results):
    """
    智能批量写入数据 - 动态调整批次大小
    """
    conn = get_db_connection()
    if not conn:
        logger.warning("Failed to get database connection for final write")
        return

    cursor = None
    try:
        cursor = conn.cursor()

        # 数据库优化设置
        cursor.execute("PRAGMA journal_mode = WAL")  # 改回WAL模式，更稳定
        cursor.execute("PRAGMA cache_size = -100000")  # 增大缓存
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA temp_store = MEMORY")

        # 动态计算批次大小，考虑内存限制
        batch_size = _calculate_batch_size(data_results)

        # 使用公共函数写入不同类型的数据
        _write_data_batch(cursor, "slice", data_results['slice'], batch_size, INSERT_SLICE_SQL)
        _write_data_batch(cursor, "counter", data_results['counter'], batch_size, INSERT_COUNTER_SQL)
        _write_data_batch(cursor, "flow", data_results['flow'], batch_size, INSERT_FLOW_SQL)

        conn.commit()
        total_written = len(data_results['slice']) + len(data_results['counter']) + len(data_results['flow'])
        logger.debug(f"Successfully written {total_written} data records")

    except Exception as e:
        logger.warning(f"Error during data writing: {e}")
        if conn:
            conn.rollback()
    finally:
        # 确保资源正确释放：先关闭cursor，再关闭conn
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _calculate_batch_size(data_results):
    """
    动态计算批次大小，考虑数据量和可用内存
    """
    # 计算总数据量
    total_records = sum(len(data) for data in data_results.values())

    # 基础批次大小
    batch_size = DEFAULT_BATCH_SIZE

    # 根据数据量调整批次大小
    if total_records > 1000000:  # 超过100万条记录
        batch_size = min(MAX_BATCH_SIZE, batch_size * 2)
    elif total_records < 100000:  # 少于10万条记录
        batch_size = max(MIN_BATCH_SIZE, batch_size // 2)

    # 检查可用内存，如果内存紧张则减小批次大小
    try:
        memory_info = psutil.virtual_memory()
        available_memory_gb = memory_info.available / (1024 ** 3)

        # 如果可用内存小于2GB，减小批次大小
        if available_memory_gb < 2:
            batch_size = max(MIN_BATCH_SIZE, batch_size // 2)
            logger.debug(f"Low memory detected ({available_memory_gb:.1f}GB), reducing batch size to {batch_size}")
    except Exception as e:
        logger.debug(f"Unable to check memory info: {e}, using default batch size")

    logger.debug(f"Using batch size: {batch_size}")
    return batch_size


def _write_data_batch(cursor, data_type, data, batch_size, insert_sql):
    """
    公共函数：批量写入数据

    Args:
        cursor: 数据库游标
        data_type: 数据类型名称（用于日志）
        data: 要写入的数据列表
        batch_size: 批次大小
        insert_sql: 插入SQL语句
    """
    if not data:
        logger.debug(f"No {data_type} data to write")
        return

    logger.debug(f"Writing {len(data)} {data_type} records")

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        cursor.executemany(insert_sql, batch)

        # 进度报告
        if (i // batch_size) % PROGRESS_REPORT_FREQUENCY == 0:
            logger.debug(f"Written {min(i + batch_size, len(data))}/{len(data)} {data_type} records")

    logger.debug(f"Completed writing {len(data)} {data_type} records")
