# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
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
from pathlib import Path
import numpy as np
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger


def is_contained_vaild_iter_info(rid_list, token_id_list):
    if rid_list is None or token_id_list is None or len(rid_list) != len(token_id_list):
        return False
    return True


def print_warning_log(log_name):
    if not ExporterSummary.get_err_log_flag(log_name):
        logger.warning(f"The '{log_name}' field info is missing, please check.")
        ExporterSummary.set_err_log_flag(log_name, True)


def process_each_record(req_map, batch_map, record):
    process_req_record(req_map, record)
    process_batch_record(batch_map, record)


def process_batch_record(batch_map, record):
    batch_type = record.get('batch_type')
    rid_tuple = str(record.get('rid_list'))

    # 构建batch_map
    if batch_type == 'Prefill':
        prefill_key = f"prefill_{rid_tuple}"
        if prefill_key not in batch_map:
            batch_map[prefill_key] = {
                'prefill_batch_num': 0,
                'prefill_exec_time (ms)': 0.0
            }
        batch_map[prefill_key]['prefill_batch_num'] = int(record.get('batch_size'))
        batch_map[prefill_key]['prefill_exec_time (ms)'] += float(record.get('during_time')) / 1000

    if batch_type == 'Decode':
        decode_key = f"decode_{rid_tuple}"
        if decode_key not in batch_map:
            batch_map[decode_key] = {
                'decode_batch_num': 0,
                'decode_exec_time (ms)': 0.0
            }
        batch_map[decode_key]['decode_batch_num'] = int(record.get('batch_size'))
        batch_map[decode_key]['decode_exec_time (ms)'] += float(record.get('during_time')) / 1000


def process_req_record(req_map, record):
    name = record.get('name')
    rid = record.get('rid')
    req_wait_status = record.get('WAITING+')
    req_pend_status = record.get('PENDING+')
    recv_token = record.get('recvTokenSize=')
    reply_token = record.get('replyTokenSize=')

    if rid is None or name is None:
        print_warning_log('rid or name')
        return

    if name == 'httpReq':
        req_map[rid] = {
            'httpReq_start': record.get('start_time'),
            'token_id': {},
            'req_waiting_time': 0.0,
            'req_pending_time': 0.0,
            'is_complete': False
        }
        return

    if name == 'httpRes':
        if rid in req_map:
            req_map[rid]['httpRes_end'] = record.get('end_time')
            req_map[rid]['is_complete'] = True
            if reply_token:
                req_map[rid]['generated_token_num'] = reply_token
        else:
            logger.warning(f"Missing httpReq for httpRes with rid={rid}.")
        return

    if req_map.get(rid) is not None:
        if name == 'httpRes':
            req_map[rid]['httpRes_end'] = record.get('end_time')

    # 队列waiting时长
    if req_wait_status == 1:
        req_map[rid]['req_waiting_time'] = record.get('during_time')

    # 队列pending时长
    if req_pend_status == 1:
        req_map[rid]['req_pending_time'] = record.get('during_time')

    # 输入Token数量为recvTokenSize的值
    if recv_token:
        req_map[rid]['input_token_num'] = recv_token

    rid_list = record.get('rid_list')
    token_id_list = record.get('token_id_list')
    process_rid_token_list(req_map, rid_list, token_id_list, record)


def process_rid_token_list(req_map, rid_list, token_id_list, record):

    if not is_contained_vaild_iter_info(rid_list, token_id_list):
        return

    for i, value in enumerate(rid_list):
        req_rid = str(int(value))
        if req_map.get(req_rid) is None:
            print_warning_log('httpReq')
            continue

        cur_iter = token_id_list[i]
        if cur_iter is None:
            print_warning_log('token_id_list')
            continue

        req_map[req_rid]['token_id'][str(cur_iter)] = record.get('end_time')

        # 首Token时延
        if cur_iter == 0:
            if req_map[req_rid].get('first_token_latency') is None:
                req_map[req_rid]['first_token_latency'] = record.get('during_time')
            else:
                req_map[req_rid]['first_token_latency'] += record.get('during_time')

        # 执行总时长
        if record.get('name') == 'modelExec':
            if req_map[req_rid].get('exec_time') is None:
                req_map[req_rid]['exec_time'] = record.get('during_time')
            else:
                req_map[req_rid]['exec_time'] += record.get('during_time')


def gen_exporter_results(all_data_df):
    req_map = {}
    batch_map = {}

    for _, record in all_data_df.iterrows():
        process_each_record(req_map, batch_map, record)

    # 生成request维度数据
    req_view, total_map = calculate_request_metrics(req_map)

    # 获取req_view数据
    first_token_latency = [req["first_token_latency"] for req in req_view]
    subsequent_token_latency = [
        latency
        for req in req_view
        for latency in req["subsequent_token_latency"]
    ]
    total_time = [req["total_time"] for req in req_view]
    exec_time = [req["exec_time"] for req in req_view]
    waiting_time = [req["waiting_time"] for req in req_view]
    input_token_num = [req["input_token_num"] for req in req_view]
    generated_token_num = [req["generated_token_num"] for req in req_view]

    #计算统计值
    req_stats = {
        "first_token_latency (ms)":calculate_statistics(first_token_latency),
        "subsequent_token_latency (ms)":calculate_statistics(subsequent_token_latency),
        "total_time (ms)":calculate_statistics(total_time),
        "exec_time (ms)":calculate_statistics(exec_time),
        "waiting_time (ms)":calculate_statistics(waiting_time),
        "input_token_num":calculate_statistics(input_token_num),
        "generated_token_num":calculate_statistics(generated_token_num)
    }

    # 生成batch维度数据
    batch_status = calculate_batch_metrics(batch_map)

    return req_stats, batch_status, total_map


def calculate_statistics(metric):
    """
    计算avg、max、min、p99、p90、p50的公共函数
    """
    if not metric or any(not isinstance(value, (int, float)) for value in metric):
        return {
            "avg": np.nan,
            "max": np.nan,
            "min": np.nan,
            "p50": np.nan,
            "p90": np.nan,
            "p99": np.nan
        }
    return {
        "avg": round(np.mean(metric), 4),
        "max": round(np.max(metric), 4),
        "min": round(np.min(metric), 4),
        "p50": round(np.percentile(metric, 50), 4),
        "p90": round(np.percentile(metric, 90), 4),
        "p99": round(np.percentile(metric, 99), 4)
    }


def calculate_batch_metrics(batch_map):
    prefill_batch_num_list = []
    decode_batch_num_list = []
    prefill_exec_time_list = []
    decode_exec_time_list = []

    for key, value in batch_map.items():
        if key.startswith('prefill'):
            prefill_batch_num_list.append(value.get('prefill_batch_num', 0))
            prefill_exec_time_list.append(value.get('prefill_exec_time (ms)', 0.0))
        elif key.startswith('decode'):
            decode_batch_num_list.append(value.get('decode_batch_num', 0))
            decode_exec_time_list.append(value.get('decode_exec_time (ms)', 0.0))

    # 计算统计指标
    batch_status = {
        "prefill_batch_num": calculate_statistics(prefill_batch_num_list),
        "decode_batch_num": calculate_statistics(decode_batch_num_list),
        "prefill_exec_time (ms)": calculate_statistics(prefill_exec_time_list),
        "decode_exec_time (ms)": calculate_statistics(decode_exec_time_list)
    }

    return batch_status


def calculate_request_metrics(req_map):
    req_view = []
    total_map = {
        "total_input_token_num": 0,
        "total_generated_token_num": 0,
        "generate_token_speed (token/s)": 0,
        "generate_all_token_speed (token/s)": 0
    }
    first_request_start_time, last_request_end_time = None, None
    for req_id, req_data in req_map.items():
        input_token_num = req_data["input_token_num"]
        generated_token_num = req_data["generated_token_num"]
        # 从字典中取出数据
        record = {
            "req_id": req_id,
            "first_token_latency": round(req_data["first_token_latency"] / 1000, 4),
            "exec_time": round(req_data["exec_time"] / 1000, 4),
            "input_token_num": input_token_num,
            "generated_token_num": generated_token_num
        }
        # 非首Token时延
        token_id = req_data["token_id"]
        subsequent_token_latency = []
        sorted_tokens = sorted(token_id.items(), key=lambda x: int(x[0]))
        for i in range(1, len(sorted_tokens)):
            current_token_time = sorted_tokens[i][1]
            previous_token_time = sorted_tokens[i - 1][1]
            latency = round((current_token_time - previous_token_time) / 1000, 4)
            subsequent_token_latency.append(latency)
        record["subsequent_token_latency"] = subsequent_token_latency

        # 总时长
        total_time = req_data["httpRes_end"] - req_data["httpReq_start"]
        total_time = total_time / 1000
        record["total_time"] = total_time

        # 队列等待时长
        waiting_time = req_data["req_pending_time"] + req_data["req_waiting_time"]
        record["waiting_time"] = waiting_time
        req_view.append(record)

        # 更新总体维度数据
        total_map["total_input_token_num"] += input_token_num
        total_map["total_generated_token_num"] += generated_token_num

        # 更新第一个请求的开始时间和最后一个请求的结束时间
        current_start_time = req_data["httpReq_start"]
        current_end_time = req_data["httpRes_end"]
        if first_request_start_time is None or current_start_time < first_request_start_time:
            first_request_start_time = current_start_time
        if last_request_end_time is None or current_end_time > last_request_end_time:
            last_request_end_time = current_end_time

        # 计算total_exec_time
        total_exec_time = round((last_request_end_time - first_request_start_time) / 1000000, 4)

        # 计算generate_token_speed和generate_all_token_speed
        if total_exec_time > 0:
            total_map["generate_token_speed (token/s)"] = total_map["total_generated_token_num"] / total_exec_time
            total_map["generate_token_speed (token/s)"] = round(total_map["generate_token_speed (token/s)"], 4)

            total_map["generate_all_token_speed (token/s)"] = (total_map["total_input_token_num"] + total_map[
                "total_generated_token_num"]) / total_exec_time
            total_map["generate_all_token_speed (token/s)"] = round(total_map["generate_all_token_speed (token/s)"], 4)

    return req_view, total_map


def save_dataframe_to_csv(map_data, output, file_name, include_stats=1):
    if output is None:
        return

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_path = output_path / file_name

    # 将map_data转换为DataFrame
    df = convert_map_to_dataframe(map_data, include_stats)

    # 保存到csv
    df.to_csv(file_path, index=False)

    os.chmod(file_path, 0o640)


def convert_map_to_dataframe(map_data, include_stats):
    data = []
    for metric, values in map_data.items():
        if include_stats == 1:
            row = {
                "Metric": metric,
                "average": values["avg"],
                "max": values["max"],
                "min":values["min"],
                "P50": values["p50"],
                "P90": values["p90"],
                "P99": values["p99"]
            }
        else:
            value = format(values, ".8f") if metric == "generate_token_speed (token/s)" else values
            row = {"Metric": metric, "value": value}
        data.append(row)
    return pd.DataFrame(data)


class ExporterSummary(ExporterBase):
    name = "summary"
    err_log = {'rid or name': False, 'start_time': False, 'httpReq': False, 'token_id_list': False}

    @classmethod
    def initialize(cls, args):
        cls.args = args
        cls.err_log = {'rid or name': False, 'start_time': False, 'httpReq': False, 'token_id_list': False}

    @classmethod
    def set_err_log_flag(cls, index, value):
        cls.err_log[index] = value

    @classmethod
    def get_err_log_flag(cls, index):
        return cls.err_log[index]

    @classmethod
    def export(cls, data) -> None:
        all_data_df = data.get('tx_data_df')

        if all_data_df is None:
            logger.warning("The data is empty, please check")
            return

        # 调用计算首Token时延的函数
        req_status, batch_status, total_map = gen_exporter_results(all_data_df)
        output = cls.args.output_path

        # 格式化存入csv
        save_dataframe_to_csv(req_status, output, "request_summary.csv")
        save_dataframe_to_csv(batch_status, output, "batch_summary.csv")
        save_dataframe_to_csv(total_map, output, "service_summary.csv", include_stats=0)
