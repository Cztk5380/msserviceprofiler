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
import os
import datetime
import sqlite3
import numpy as np
from ms_service_profiler.exporters.base import ExporterBase


req_map = {}


def timestamp_converter(timestamp):
    """
    将传入的科学计数法的时间戳转换为真实时间，并在后续处理中存入kvcache.db文件中
    :param timestamp: 科学计数法时间戳
    :return: 真实时间
    """
    # 传入数据为科学计数法的时间戳数据
    timestamp_sci = timestamp

    # 将科学计数法的时间戳转换为Decimal类型
    timestamp_normal = Decimal(timestamp_sci)

    # 将Decimal类型转换为浮点数类型，以便后续能被fromtimestamp函数正确使用
    timestamp_seconds = float(timestamp_normal / 1000000)

    # 将秒数转换为datetime对象
    date_time = datetime.datetime.fromtimestamp(timestamp_seconds)

    return date_time.strftime("%Y-%m-%d %H:%M:%S:%f")


def process_each_record(record):
    global req_map
    name = record['name']
    rid = record['rid']
    if name == 'httpReq':
        req_map[rid] = {}
        req_map[rid]['start_time'] = record['start_time']
    elif name == 'httpRes':
        req_map[rid]['end_time'] = record['end_time']
        req_map[rid]['gen_last_token_time'] = record['end_time']

    rid_list = record['rid_list']
    token_id_list = record['token_id_list']
    if rid_list is None or token_id_list is None:
        return

    for i, value in enumerate(rid_list):
        req_rid = str(int(value))
        cur_iter = token_id_list[i]

        if cur_iter == 0:
            if req_map[req_rid].get('first_token_latency') is None:
                req_map[req_rid]['first_token_latency'] = record['during_time']
            else:
                req_map[req_rid]['first_token_latency'] += record['during_time']

        gen_token_num = cur_iter + 1
        if req_map[req_rid].get('gen_token_num') is None or req_map[req_rid]['gen_token_num'] < gen_token_num:
            req_map[req_rid]['gen_token_num'] = gen_token_num
            req_map[req_rid]['gen_last_token_time'] = record['end_time']


def get_percentile_results(metric):
    if len(metric) == 0:
        return {}
    avg = round(np.average(metric), 4)
    p99 = round(np.percentile(metric, 99), 4)
    p90 = round(np.percentile(metric, 90), 4)
    p50 = round(np.percentile(metric, 50), 4)
    metric_results = {'avg': avg, 'p99': p99, 'p90': p90, 'p50': p50}
    return metric_results


def calculate_first_token_latency():
    first_token_latency = []
    for rid in req_map:
        # 计算首token时延，µs级
        if req_map[rid].get('first_token_latency') is not None:
            first_token_latency.append(round(req_map[rid]['first_token_latency'], 4))
    
    return get_percentile_results(first_token_latency)


def calculate_req_latency():
    req_latency = []
    for rid in req_map:
        cur_req_start_time = req_map[rid]['start_time']

        # 计算请求端到端时延，µs级
        if req_map[rid].get('end_time') is not None:
            cur_req_end_time = req_map[rid]['end_time']
            cur_req_latency = cur_req_end_time - cur_req_start_time
            req_latency.append(round(cur_req_latency, 4))
    return get_percentile_results(req_latency)


def calculate_gen_token_speed_latency():
    gen_token_speed = []
    min_start_time = float('inf')
    for rid in req_map:
        cur_req_start_time = req_map[rid]['start_time']
        min_start_time = min([min_start_time, cur_req_start_time])

        # 计算token平均时延，s级
        cur_req_gen_token_num = req_map[rid]['gen_token_num']
        gen_last_token_time = req_map[rid]['gen_last_token_time']
        diff_time = gen_last_token_time - min_start_time
        cur_gen_speed = round(cur_req_gen_token_num / (diff_time / 1000000), 4) # 1000000:换算为秒级
        gen_token_speed.append(cur_gen_speed)

    return get_percentile_results(gen_token_speed)


def gen_exporter_results(all_data_df):
    first_token_latency_view_data = {}
    req_latency_view_data = {}
    gen_token_speed_view_data = {}

    for _, record in all_data_df.iterrows():
        process_each_record(record)

        # 生成首token时延
        if record['batch_type'] == 'Prefill':
            first_token_latency_results = calculate_first_token_latency()
            cur_timestamp = timestamp_converter(record['end_time'])
            first_token_latency_view_data[cur_timestamp] = first_token_latency_results

        # 生成请求端到端时延
        if record['name'] == 'httpRes':
            req_latency_results = calculate_req_latency()
            cur_timestamp = timestamp_converter(record['end_time'])
            req_latency_view_data[cur_timestamp] = req_latency_results

        # 生成token平均时延
        if record['rid_list'] is not None:
            gen_token_speed_results = calculate_gen_token_speed_latency()
            cur_timestamp = timestamp_converter(record['end_time'])
            gen_token_speed_view_data[cur_timestamp] = gen_token_speed_results

    return first_token_latency_view_data, req_latency_view_data, gen_token_speed_view_data


def save_to_sqlite_db(table_name, view_data):
    current_path = os.path.dirname(os.path.abspath(__file__))
    # 创建output文件夹
    output_folder = os.path.join(current_path, 'output')
    db_file = os.path.join(output_folder, 'profiler.db')
    conn = sqlite3.connect(db_file)
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

        first_token_latency_view_data, req_latency_view_data, gen_token_speed_view_data = \
            gen_exporter_results(all_data_df)

        save_to_sqlite_db('first_token_latency', first_token_latency_view_data)
        save_to_sqlite_db('req_latency', req_latency_view_data)
        save_to_sqlite_db('gen_speed', gen_token_speed_view_data)
