# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import numpy as np
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import write_result_to_db, CURVE_VIEW_NAME_LIST, check_domain_valid
from ms_service_profiler.utils.timer import timer


def is_contained_vaild_iter_info(rid_list, token_id_list):
    if rid_list is None or token_id_list is None or len(rid_list) != len(token_id_list):
        return False

    return True


def print_warning_log(log_name):
    if not ExporterLatency.get_err_log_flag(log_name):
        logger.warning(f"The '{log_name}' field info is missing in prof data, please check.")
        ExporterLatency.set_err_log_flag(log_name, True)


def process_each_record(req_map, record):
    name = record.get('name')
    rid = record.get('rid')
    if rid is None or name is None:
        return

    if name == 'httpReq':
        req_map[rid] = {}
        req_map[rid]['start_time'] = record.get('start_time')
        return

    if req_map.get(rid) is not None:
        if name == 'httpRes':
            req_map[rid]['end_time'] = record.get('end_time')
        req_map[rid]['req_exec_time'] = record.get('end_time')

    rid_list = record.get('rid_list')
    token_id_list = record.get('token_id_list')
    if not is_contained_vaild_iter_info(rid_list, token_id_list):
        return

    for i, value in enumerate(rid_list):
        req_rid = str(value)
        if req_map.get(req_rid) is None:
            print_warning_log('httpReq')
            continue

        req_map[req_rid]['req_exec_time'] = record.get('end_time')

        # 更新请求首token时延
        cur_iter = token_id_list[i]
        if cur_iter is None:
            continue

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
    if not metric or any(not isinstance(value, (int, float)) for value in metric):
        return np.nan, np.nan, np.nan, np.nan
    avg = round(np.average(metric), 4)
    p50, p90, p99 = np.round(np.percentile(metric, [50, 90, 99]), 4)
    return avg, p50, p90, p99


def calculate_first_token_latency(req_map):
    first_token_latency = []
    for _, req_info in req_map.items():
        # 计算首token时延，µs级
        if req_info.get('first_token_latency') is not None:
            first_token_latency.append(round(req_info['first_token_latency'], 4))
    
    return get_percentile_results(first_token_latency)


def calculate_req_latency(req_map):
    req_latency = []
    for _, req_info in req_map.items():
        if req_info.get('start_time') is None:
            print_warning_log('start_time')
            continue
        cur_req_start_time = req_info['start_time']

        # 计算请求端到端时延，µs级
        if req_info.get('end_time') is not None:
            cur_req_end_time = req_info['end_time']
            cur_req_latency = cur_req_end_time - cur_req_start_time
            req_latency.append(round(cur_req_latency, 4))
    return get_percentile_results(req_latency)


def calculate_gen_token_speed_latency(req_map, is_prefill):
    gen_token_speed = []
    for _, req_info in req_map.items():
        if req_info.get('start_time') is None:
            print_warning_log('start_time')
            continue
        cur_req_start_time = req_info['start_time']

        cur_req_gen_token_num = 0
        try:
            if is_prefill:
                # 计算prefill token平均时延
                cur_req_gen_token_num = req_info['prefill_token_num']
            else:
                # 计算decode token平均时延
                cur_req_gen_token_num = req_info['decode_token_num']

            # 计算生成token执行时间
            gen_last_token_time = req_info['req_exec_time']
            if gen_last_token_time <= cur_req_start_time:
                raise ValueError("The execution time for generating the token is a negative number.")
            diff_time = gen_last_token_time - cur_req_start_time

            # 计算生成token平均时延，s级
            cur_gen_speed = round(cur_req_gen_token_num / (diff_time / 1000000), 4) # 1000000:换算为秒级
            gen_token_speed.append(cur_gen_speed)
        except KeyError:
            # 并发场景下，若请求到达后还未生成token，则跳过当前请求不计算
            continue

    return get_percentile_results(gen_token_speed)


def gen_exporter_results(all_data_df):
    req_map = {}
    first_token_latency_views = []
    req_latency_views = []
    prefill_gen_speed_views = []
    decode_gen_speed_views = []

    for _, record in all_data_df.iterrows():
        process_each_record(req_map, record)

        # 生成首token时延
        if record.get('batch_type') == 'Prefill':
            avg, p50, p90, p99 = calculate_first_token_latency(req_map)
            cur_timestamp = record.get('end_datetime')
            first_token_latency_views.append({'timestamp': cur_timestamp, \
                'avg': avg, 'p99': p99, 'p90': p90, 'p50': p50})

        # 生成请求端到端时延
        if record.get('name') == 'httpRes':
            avg, p50, p90, p99 = calculate_req_latency(req_map)
            cur_timestamp = record.get('end_datetime')
            req_latency_views.append({'timestamp': cur_timestamp, \
                'avg': avg, 'p99': p99, 'p90': p90, 'p50': p50})

        # 生成token平均时延
        if is_contained_vaild_iter_info(record.get('rid_list'), record.get('token_id_list')):
            cur_timestamp = record.get('end_datetime')
            if record.get('batch_type') == 'Prefill':
                avg, p50, p90, p99 = calculate_gen_token_speed_latency(req_map, True)
                prefill_gen_speed_views.append({'timestamp': cur_timestamp, \
                    'avg': avg, 'p99': p99, 'p90': p90, 'p50': p50})
            if record.get('batch_type') == 'Decode':
                avg, p50, p90, p99 = calculate_gen_token_speed_latency(req_map, False)
                decode_gen_speed_views.append({'timestamp': cur_timestamp, \
                    'avg': avg, 'p99': p99, 'p90': p90, 'p50': p50})

    return first_token_latency_views, req_latency_views, prefill_gen_speed_views, decode_gen_speed_views


class ExporterLatency(ExporterBase):
    name = "latency"
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
    
    @staticmethod
    def gen_exporter_percentile_of_df(df, order_col_name, value_col_name, max_points=100):
        if df.empty or order_col_name not in df.columns or value_col_name not in df.columns:
            return []
        sorted_series = df.groupby(order_col_name)[value_col_name].agg(list).sort_index()

        percentile_views = []
        ordered_array = np.array([], dtype=float)

        # 如果数据点超过max_points，则只取等间距的点
        total_points = len(sorted_series)
        if total_points > max_points > 0:
            # 计算采样间隔
            step = total_points // max_points
            selected_indices = range(0, total_points, step)[:max_points]
            selected_items = [list(sorted_series.items())[i] for i in selected_indices]
        else:
            selected_items = list(sorted_series.items())

        for end_time, ttft_list in selected_items:
            ordered_array = np.append(ordered_array, ttft_list)
            p50, p90, p99 = np.round(np.percentile(ordered_array, [50, 90, 99]), 2)
            avg = round(np.average(ordered_array), 2)

            percentile_views.append({'timestamp': end_time,
                                     'avg': avg, 'p99': p99, 'p90': p90, 'p50': p50})

        return percentile_views

    @staticmethod
    @timer(log_func=logger.debug)
    def gen_exporter_first_token_latency_views(req_ttft_df):
        return ExporterLatency.gen_exporter_percentile_of_df(req_ttft_df, 'end_time', 'ttft')

    @staticmethod
    @timer(log_func=logger.debug)
    def gen_exporter_req_latency_views(req_event_df):
        calc_df = req_event_df[req_event_df["event"].isin(["httpReq", "httpRes", "DecodeEnd"])]

        # 取最开始的时间和最后时间差
        group_by_df = calc_df.groupby("rid").agg({"start_time": "min", "end_time": "max", "event": ["first", 'count']})

        # 过滤掉没有 httpReq 和 只有 httpReq 的
        req_latency_df = group_by_df[(group_by_df["event"]["count"] > 1) & (group_by_df["event"]["first"] == 'httpReq')]
        req_latency_df["req_latency"] = req_latency_df["end_time"]["max"] - req_latency_df["start_time"]["min"]
        req_latency_df = req_latency_df.drop(columns=["event"])
        req_latency_df.columns = req_latency_df.columns.map(lambda x: x[0])

        return ExporterLatency.gen_exporter_percentile_of_df(req_latency_df, 'end_time', 'req_latency')

    @staticmethod
    @timer(log_func=logger.debug)
    def gen_exporter_decode_gen_speed_views(req_event_df):
        calc_df = req_event_df[req_event_df["event"].isin(["modelExec", "Execute"])]

        sorted_calc_df = calc_df.sort_values(['rid', 'start_time'])

        # 计算当前 modelExec 到上一个 modelExec 的时间
        sorted_calc_df['decode_gen_speed'] = sorted_calc_df['end_time'] - sorted_calc_df['end_time'].shift(1)
        sorted_calc_df['iter_diff'] = sorted_calc_df['iter'] - sorted_calc_df['iter'].shift(1)

        # 去除头一个
        sorted_calc_df.loc[sorted_calc_df.groupby('rid').cumcount() == 0, 'decode_gen_speed'] = np.nan
        # 去除iter不挨着的
        sorted_calc_df.loc[~sorted_calc_df["iter_diff"].isin([0, 1]), 'decode_gen_speed'] = np.nan

        # 去掉
        decode_gen_speed_df = sorted_calc_df[sorted_calc_df['decode_gen_speed'].notna()]
        return ExporterLatency.gen_exporter_percentile_of_df(decode_gen_speed_df, 'end_time', 'decode_gen_speed')

    @classmethod
    @timer(logger.debug)
    def export(cls, data) -> None:
        if 'db' not in cls.args.format:
            return

        all_data_df = data['tx_data_df']
        
        if check_domain_valid(all_data_df, ['ModelExecute', 'BatchSchedule', 'Request'], 'latency') is False:
            return

        first_token_latency_views = ExporterLatency.gen_exporter_first_token_latency_views(
            data.get("req_ttft_df", pd.DataFrame()))
        req_latency_views = ExporterLatency.gen_exporter_req_latency_views(
            data.get("req_event_df", pd.DataFrame()))
        prefill_gen_speed_views = first_token_latency_views
        decode_gen_speed_views = ExporterLatency.gen_exporter_decode_gen_speed_views(
            data.get("req_event_df", pd.DataFrame()))

        df_param_list = [
            [pd.DataFrame(first_token_latency_views), 'first_token_latency'],
            [pd.DataFrame(req_latency_views), 'req_latency'],
            [pd.DataFrame(prefill_gen_speed_views), 'prefill_gen_speed'],
            [pd.DataFrame(decode_gen_speed_views), 'decode_gen_speed']
        ]
        view_sql_list = [
            CREATE_FIRST_TOKEN_LATENCY_SQL, CREATE_REQUEST_LATENCY_SQL,
            CREATE_PREFILL_GEN_SPEED_VIEW_SQL, CREATE_DECODE_GEN_SPEED_SQL
        ]
        write_result_to_db(
            df_param_list=df_param_list,
            create_view_sql=view_sql_list
        )


CREATE_PREFILL_GEN_SPEED_VIEW_SQL = f"""
    CREATE VIEW {CURVE_VIEW_NAME_LIST['prefill_gen_speed']} AS
    WITH converted AS (
        SELECT
            substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS datetime,
            avg, p99, p90, p50
    FROM
        prefill_gen_speed
    )
    SELECT
        datetime as time,
        cast(avg as REAL) as "avg",
        cast(p99 as REAL) as "p99",
        cast(p90 as REAL) as "p90",
        cast(p50 as REAL) as "p50"
    FROM
        converted
    ORDER BY
        datetime ASC
"""


CREATE_REQUEST_LATENCY_SQL = f"""
    CREATE VIEW {CURVE_VIEW_NAME_LIST['req_latency']} AS
    WITH converted AS (
        SELECT
            substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS datetime,
            avg,
            p99,
            p90,
            p50
        FROM
            req_latency
    )
    SELECT
        datetime as time,
        cast(avg as REAL) as "avg",
        cast(p99 as REAL) as "p99",
        cast(p90 as REAL) as "p90",
        cast(p50 as REAL) as "p50"
    FROM
        converted
    ORDER BY
        datetime ASC
"""

CREATE_DECODE_GEN_SPEED_SQL = f"""
    CREATE VIEW {CURVE_VIEW_NAME_LIST['decode_gen_speed']} AS
    WITH converted AS (
        SELECT
            substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS datetime,
            avg, p99, p90, p50
    FROM
        decode_gen_speed
    )
    SELECT
        datetime as time,
        cast(avg as REAL) as "avg",
        cast(p99 as REAL) as "p99",
        cast(p90 as REAL) as "p90",
        cast(p50 as REAL) as "p50"
    FROM
        converted
    ORDER BY
        datetime ASC
"""

CREATE_FIRST_TOKEN_LATENCY_SQL = f"""
    CREATE VIEW {CURVE_VIEW_NAME_LIST['first_token_latency']} AS
    WITH converted AS (
        SELECT
        substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS datetime,
        avg, p99, p90, p50
    FROM
        first_token_latency
    )
    SELECT
        datetime as time,
        cast(avg as REAL) as "avg",
        cast(p99 as REAL) as "p99",
        cast(p90 as REAL) as "p90",
        cast(p50 as REAL) as "p50"
    FROM
        converted
    ORDER BY
        datetime ASC
"""
