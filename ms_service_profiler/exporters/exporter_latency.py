# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import datetime
from decimal import Decimal
import sqlite3
import numpy as np
from ms_service_profiler.exporters.base import ExporterBase


def timestamp_converter(timestamp):
    timestamp_sci = timestamp
    timestamp_normal = Decimal(timestamp_sci)

    # 1000000: 将Decimal类型转换为浮点数类型，以便后续能被fromtimestamp函数正确使用
    timestamp_seconds = float(timestamp_normal / 1000000)
    date_time = datetime.datetime.fromtimestamp(timestamp_seconds)
    return date_time.strftime("%Y-%m-%d %H:%M:%S:%f")


def set_generate_token_info(req_map, req_rid, record):
    if req_map[req_rid].get('gen_token_num') is None or req_map[req_rid]['gen_token_num'] < gen_token_num:
        if record.get('batch_type') == 'Prefill':
            req_map[req_rid]['prefill_token_num'] = gen_token_num
            req_map[req_rid]['prefill_last_token_time'] = record.get('end_time')


def is_contained_vaild_iter_info(rid_list, token_id_list):
    if rid_list is None or token_id_list is None or len(rid_list) != len(token_id_list):
        return False

    return True


def process_each_record(req_map, record):
    name = record.get('name')
    rid = record.get('rid')
    if rid is None or name is None:
        return

    if name == 'httpReq':
        req_map[rid] = {}
        req_map[rid]['start_time'] = record.get('start_time')

    if req_map.get(rid) is not None:
        if name == 'httpRes':
            req_map[rid]['end_time'] = record.get('end_time')
        req_map[rid]['req_exec_time'] = record.get('end_time')

    rid_list = record.get('rid_list')
    token_id_list = record.get('token_id_list')
    if not is_contained_vaild_iter_info(rid_list, token_id_list):
        return

    for i, value in enumerate(rid_list):
        req_rid = str(int(value))
        if req_map.get(req_rid) is None:
            continue

        req_map[req_rid]['req_exec_time'] = record.get('end_time')

        # 更新请求首token时延
        cur_iter = token_id_list[i]
        if cur_iter == 0:
            if req_map[req_rid].get('first_token_latency') is None:
                req_map[req_rid]['first_token_latency'] = record.get('during_time')
            else:
                req_map[req_rid]['first_token_latency'] += record.get('during_time')

        # 更新请求生成token数量
        gen_token_num = cur_iter + 1
        if record.get('batch_type') == 'Prefill':
            if req_map[req_rid].get('prefill_token_num') is None or \
                req_map[req_rid]['prefill_token_num'] < gen_token_num:
                req_map[req_rid]['prefill_token_num'] = gen_token_num
        elif record.get('batch_type') == 'Decode':
            if req_map[req_rid].get('decode_token_num') is None or \
                req_map[req_rid]['decode_token_num'] < gen_token_num:
                req_map[req_rid]['decode_token_num'] = gen_token_num


def get_percentile_results(metric):
    if len(metric) == 0:
        return {}
    avg = round(np.average(metric), 4)
    p99 = round(np.percentile(metric, 99), 4)
    p90 = round(np.percentile(metric, 90), 4)
    p50 = round(np.percentile(metric, 50), 4)
    metric_results = {'avg': avg, 'p99': p99, 'p90': p90, 'p50': p50}
    return metric_results


def calculate_first_token_latency(req_map):
    first_token_latency = []
    for rid in req_map:
        # 计算首token时延，µs级
        if req_map[rid].get('first_token_latency') is not None:
            first_token_latency.append(round(req_map[rid]['first_token_latency'], 4))
    
    return get_percentile_results(first_token_latency)


def calculate_req_latency(req_map):
    req_latency = []
    for rid in req_map:
        cur_req_start_time = req_map[rid]['start_time']

        # 计算请求端到端时延，µs级
        if req_map[rid].get('end_time') is not None:
            cur_req_end_time = req_map[rid]['end_time']
            cur_req_latency = cur_req_end_time - cur_req_start_time
            req_latency.append(round(cur_req_latency, 4))
    return get_percentile_results(req_latency)


def calculate_gen_token_speed_latency(req_map, is_prefill):
    gen_token_speed = []
    for rid in req_map:
        cur_req_start_time = req_map[rid]['start_time']

        cur_req_gen_token_num = 0
        if is_prefill:
            # 计算prefill token平均时延
            cur_req_gen_token_num = req_map[rid]['prefill_token_num']
        else:
            # 计算decode token平均时延
            cur_req_gen_token_num = req_map[rid]['decode_token_num']

        # 计算生成token执行时间
        gen_last_token_time = req_map[rid]['req_exec_time']
        if gen_last_token_time <= cur_req_start_time:
            raise ValueError("The execution time for generating the token is a negative number.")
        diff_time = gen_last_token_time - cur_req_start_time

        # 计算生成token平均时延，s级
        cur_gen_speed = round(cur_req_gen_token_num / (diff_time / 1000000), 4) # 1000000:换算为秒级
        gen_token_speed.append(cur_gen_speed)

    return get_percentile_results(gen_token_speed)


def gen_exporter_results(all_data_df):
    req_map = {}
    first_token_latency_views = {}
    req_latency_views = {}
    prefill_gen_token_speed_views = {}
    decode_gen_token_speed_views = {}

    for _, record in all_data_df.iterrows():
        process_each_record(req_map, record)

        # 生成首token时延
        if record.get('batch_type') == 'Prefill':
            first_token_latency_results = calculate_first_token_latency(req_map)
            cur_timestamp = timestamp_converter(record.get('end_time'))
            first_token_latency_views[cur_timestamp] = first_token_latency_results

        # 生成请求端到端时延
        if record.get('name') == 'httpRes':
            req_latency_results = calculate_req_latency(req_map)
            cur_timestamp = timestamp_converter(record.get('end_time'))
            req_latency_views[cur_timestamp] = req_latency_results

        # 生成token平均时延
        if is_contained_vaild_iter_info(record.get('rid_list'), record.get('token_id_list')):
            cur_timestamp = timestamp_converter(record.get('end_time'))
            if record.get('batch_type') == 'Prefill':
                prefill_gen_token_speed_views[cur_timestamp] = calculate_gen_token_speed_latency(req_map, True)
            if record.get('batch_type') == 'Decode':
                decode_gen_token_speed_views[cur_timestamp] = calculate_gen_token_speed_latency(req_map, False)

    return first_token_latency_views, req_latency_views, prefill_gen_token_speed_views, decode_gen_token_speed_views


def create_sqlite_db(output):
    if not os.path.exists(output):
        os.makedirs(output)

    db_file = os.path.join(output, '.profiler.db')
    conn = sqlite3.connect(db_file)
    conn.isolation_level = None
    cursor = conn.cursor()
    conn.close()
    return db_file


def save_to_sqlite_db(db_file_path, table_name, view_data):
    conn = sqlite3.connect(db_file_path)
    cursor = conn.cursor()
    cursor.execute(f'DROP TABLE IF EXISTS {table_name}')  # 删除旧表
    cursor.execute(f'CREATE TABLE {table_name} (timestamp TEXT, avg REAL, \
        p99 REAL, p90 REAL, p50 REAL)')
    for timestamp, data in view_data.items():
        avg = data.get('avg')
        p99 = data.get('p99')
        p90 = data.get('p90')
        p50 = data.get('p50')
        cursor.execute(f'INSERT INTO {table_name} VALUES (?, ?, ?, ?, ?)', \
                       (timestamp, avg, p99, p90, p50))
    conn.commit()
    conn.close()


class ExporterLatency(ExporterBase):
    name = "latency"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        all_data_df = data['tx_data_df']
        output = cls.args.output_path

        first_token_latency_views, req_latency_views, prefill_gen_speed_views, decode_gen_speed_views = \
            gen_exporter_results(all_data_df)

        db_file_path = create_sqlite_db(output)
        save_to_sqlite_db(db_file_path, 'first_token_latency', first_token_latency_views)
        save_to_sqlite_db(db_file_path, 'req_latency', req_latency_views)
        save_to_sqlite_db(db_file_path, 'prefill_gen_speed', prefill_gen_speed_views)
        save_to_sqlite_db(db_file_path, 'decode_gen_speed', decode_gen_speed_views)
