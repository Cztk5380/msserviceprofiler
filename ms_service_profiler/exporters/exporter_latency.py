# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from dataclasses import dataclass
from typing import List, Optional, Callable

import numpy as np
import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import (
    write_result_to_db, check_domain_valid,
    TableConfig, CurveViewConfig
)
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.parse_helper.utils import convert_timestamp
from ms_service_profiler.plugins.plugin_timestamp import timestamp_converter


@dataclass
class TimeIntervalConfig:
    """时间间隔分组配置"""
    time_interval_us: int = 100000
    timestamp_converter_func: Callable = timestamp_converter
    required_stats_fields: Optional[List[str]] = None
    include_global_stats: bool = False

    def __post_init__(self):
        if self.required_stats_fields is None:
            self.required_stats_fields = ['p50', 'p90', 'p99', 'avg', 'min_value', 'max_value']


class ExporterLatency(ExporterBase):
    name = "latency"
    err_log = {'rid or name': False, 'start_time': False, 'httpReq': False, 'token_id_list': False}

    @staticmethod
    def gen_exporter_percentile_of_df(df, order_col_name, value_col_name, max_points=100):
        if df.empty or order_col_name not in df.columns or value_col_name not in df.columns:
            return []
        sorted_series = df.groupby(order_col_name)[value_col_name].agg(list).sort_index()
        all_items = list(sorted_series.items())

        percentile_views = []
        all_data = []  # 收集所有数据

        # 先收集所有数据
        for _, ttft_list in all_items:
            all_data.extend(ttft_list)

        # 转换为numpy数组
        all_data = np.array(all_data)

        # 计算全局p50_alltime值
        global_p50 = None
        if len(all_data) > 0:
            global_p50 = np.percentile(all_data, 50)
            logger.debug(f"Global p50_alltime for {value_col_name}: {global_p50}")

        # 计算累积统计
        current_count = 0
        calculation_interval = max(len(all_items) // max_points, 1)  # 根据max_points控制计算频率

        for index, (end_time, ttft_list) in enumerate(all_items):
            current_count += len(ttft_list)
            # 当时间点数量 <= max_points时：每个时间点都会计算（calculation_interval=1）
            # 当时间点数量 > max_points时：均匀分布地选择约max_points个时间点进行计算
            if (index + 1) % calculation_interval == 0 or index == len(all_items) - 1:
                # 获取到当前为止的所有数据
                current_data = all_data[:current_count]
                p50, p90, p99 = np.round(np.percentile(current_data, [50, 90, 99]), 2)
                avg = round(np.average(current_data), 2)

                view_item = {
                    'timestamp': convert_timestamp(end_time),
                    'avg': avg,
                    'p99': p99,
                    'p90': p90,
                    'p50': p50
                }

                # 添加全局p50_alltime
                if global_p50 is not None:
                    view_item['p50_alltime'] = global_p50

                percentile_views.append(view_item)

        return percentile_views

    @staticmethod
    @timer(log_func=logger.debug)
    def gen_exporter_req_latency_views(req_event_df):
        calc_df = req_event_df[req_event_df["event"].isin(["httpReq", "httpRes", "DecodeEnd", "FINISHED"])]

        # 取最开始的时间和最后时间差
        group_by_df = calc_df.groupby("rid").agg({"start_time": "min", "end_time": "max", "event": ["first", 'count']})

        # 过滤掉没有 httpReq 和 只有 httpReq 的
        req_latency_df = (
            group_by_df[(group_by_df["event"]["count"] > 1) & (group_by_df["event"]["first"] == 'httpReq')]
            .copy())
        req_latency_df.loc[:, "req_latency"] = req_latency_df["end_time"]["max"] - req_latency_df["start_time"]["min"]
        req_latency_df = req_latency_df.drop(columns=["event"])
        req_latency_df.columns = req_latency_df.columns.map(lambda x: x[0])

        return ExporterLatency.gen_exporter_percentile_of_df(req_latency_df, 'end_time', 'req_latency')

    @staticmethod
    @timer(log_func=logger.debug)
    def gen_exporter_first_token_latency_views(req_ttft_df):
        """
        生成按固定时间间隔分组的TTFT性能视图（均匀时间序列）
        """
        if req_ttft_df.empty:
            logger.debug("req_ttft_df is empty")
            return []

        # 确保ttft为数值类型
        req_ttft_df = req_ttft_df.copy()
        req_ttft_df['ttft'] = pd.to_numeric(req_ttft_df['ttft'], errors='coerce')

        # 调试：打印原始ttft统计信息
        logger.debug(
            f"Original ttft stats: min={req_ttft_df['ttft'].min()}, "
            f"max={req_ttft_df['ttft'].max()}, mean={req_ttft_df['ttft'].mean()}")

        # 去除无效数据
        req_ttft_df = req_ttft_df.dropna(subset=['ttft', 'start_time'])

        if req_ttft_df.empty:
            logger.debug("req_ttft_df is empty after filtering")
            return []

        config = TimeIntervalConfig(
            time_interval_us=100000,
            timestamp_converter_func=timestamp_converter,
            required_stats_fields=['p99', 'p90', 'p50', 'min_value'],
            include_global_stats=True  # 包含全局统计值
        )

        return ExporterLatency._group_by_time_intervals(
            req_ttft_df, 'start_time', 'ttft', config
        )

    @staticmethod
    @timer(log_func=logger.debug)
    def gen_exporter_prefill_gen_speed_views(req_event_df):
        """
        生成预填充生成速度视图（包含基础数据和时间分组统计）
        """

        def event_filter(df):
            return df["event"].isin(["BatchSchedule", "Execute"])

        # 获取基础速度数据
        speed_data = ExporterLatency._calculate_speed_from_events(
            req_event_df, event_filter, ExporterLatency._calculate_prefill_speed_logic
        )

        if not speed_data:
            return []

        # 转换为 DataFrame
        speed_df = pd.DataFrame(speed_data)

        if speed_df.empty:
            return []

        config = TimeIntervalConfig(
            time_interval_us=100000,
            timestamp_converter_func=convert_timestamp,
            required_stats_fields=['avg', 'p99', 'p90', 'p50'],  # 生成速度只需要基本统计
            include_global_stats=True  # 包含全局统计值
        )

        # 计算时间分组统计
        return ExporterLatency._group_by_time_intervals(
            speed_df, 'timestamp_numeric', 'prefill_gen_speed', config
        )

    @staticmethod
    @timer(log_func=logger.debug)
    def gen_exporter_decode_gen_speed_views(req_event_df):

        def event_filter(df):
            return df["event"] == "Execute"

        # 获取基础速度数据
        speed_data = ExporterLatency._calculate_speed_from_events(
            req_event_df, event_filter, ExporterLatency._calculate_decode_speed_logic
        )

        if not speed_data:
            return []

        speed_df = pd.DataFrame(speed_data)

        if speed_df.empty:
            return []

        config = TimeIntervalConfig(
            time_interval_us=100000,
            timestamp_converter_func=convert_timestamp,
            required_stats_fields=['avg', 'p99', 'p90', 'p50'],
            include_global_stats=True  # 包含全局统计值
        )

        # 计算时间分组统计
        return ExporterLatency._group_by_time_intervals(
            speed_df, 'timestamp_numeric', 'decode_gen_speed', config
        )

    @staticmethod
    def _calculate_all_statistics(data_series):
        """计算数据系列的所有统计值"""
        if len(data_series) == 0:
            return None

        p50 = np.percentile(data_series, 50)
        p90 = np.percentile(data_series, 90)
        p99 = np.percentile(data_series, 99)
        avg = np.mean(data_series)
        min_val = np.min(data_series)
        max_val = np.max(data_series)

        return {
            'p50': p50,
            'p90': p90,
            'p99': p99,
            'avg': avg,
            'min_value': min_val,
            'max_value': max_val
        }

    @staticmethod
    def _calculate_statistics_with_fields(data_series, required_fields, global_stats=None):
        """计算数据系列的统计值，只返回需要的字段，支持添加全局统计值"""
        if len(data_series) == 0:
            return None

        all_stats = ExporterLatency._calculate_all_statistics(data_series)
        if all_stats:
            result = {k: v for k, v in all_stats.items() if k in required_fields}

            # 如果提供了全局统计值，添加到结果中
            if global_stats:
                result.update(global_stats)

            return result
        return None

    @staticmethod
    def _group_by_time_intervals(df, time_col, value_col, config: TimeIntervalConfig):
        """按固定时间间隔对数据进行分组并计算统计值"""
        if df.empty:
            return []

        base_time = df[time_col].min()
        end_time = df[time_col].max()

        # 计算时间窗口
        total_duration_us = end_time - base_time
        total_time_points = int(total_duration_us // config.time_interval_us) + 1

        # 边界检查：确保最后一个窗口包含end_time
        last_window_end = base_time + total_time_points * config.time_interval_us
        if end_time > last_window_end:
            total_time_points = int((end_time - base_time) // config.time_interval_us) + 1

        logger.debug(
            f"Time range: {base_time} to {end_time}, duration={total_duration_us} us, windows={total_time_points}")
        logger.debug(f"Base time: {base_time} -> {config.timestamp_converter_func(base_time)}")

        # 创建时间窗口边界
        time_bins = [base_time + i * config.time_interval_us for i in range(total_time_points + 1)]

        # 使用pd.cut进行向量化分组
        df_copy = df.copy()
        df_copy['time_bin'] = pd.cut(df_copy[time_col], bins=time_bins, right=False, include_lowest=True)

        # 过滤掉未分配到窗口的数据（理论上不应该有，但作为安全措施）
        df_copy = df_copy.dropna(subset=['time_bin'])

        # 按时间窗口分组并计算统计值
        grouped = df_copy.groupby('time_bin')[value_col]

        result_data = []

        # 计算全局统计值 - 只计算p50
        global_stats = {}
        if config.include_global_stats:
            all_values = df[value_col].dropna()
            if len(all_values) > 0:
                # 只计算全局p50值
                global_p50 = np.percentile(all_values, 50)
                global_stats = {'p50_alltime': global_p50}
                logger.debug(f"Global p50 calculated: {global_p50}")

        # 遍历每个时间窗口
        for time_bin, window_data in grouped:
            if len(window_data) == 0:
                continue

            # 从时间区间获取左边界时间点
            current_time = time_bin.left

            logger.debug(f"=== Window ===")
            logger.debug(f"Time range: {current_time} - {time_bin.right}")
            logger.debug(
                f"Time range converted: {config.timestamp_converter_func(current_time)} - "
                f"{config.timestamp_converter_func(time_bin.right)}")
            logger.debug(f"Requests in window: {len(window_data)}")

            logger.debug(f"Window data values: {window_data.tolist()}")
            logger.debug(f"Window  min={window_data.min()}, max={window_data.max()}, mean={window_data.mean()}")

            stats = ExporterLatency._calculate_statistics_with_fields(window_data,
                                                                      config.required_stats_fields,
                                                                      global_stats)

            if stats:  # 只有当stats不为None时才添加到结果中
                logger.debug(
                    f"Calculated values: avg={stats.get('avg')}, p50={stats.get('p50')}, "
                    f"p90={stats.get('p90')}, p99={stats.get('p99')}")
                # 全局统计值
                global_keys = [k for k in stats.keys() if k.endswith('_alltime')]
                if global_keys:
                    logger.debug(f"Global values added: {[f'{k}={stats[k]}' for k in global_keys]}")

                # 计算时间戳
                timestamp = config.timestamp_converter_func(current_time)

                result_data.append({'timestamp': timestamp, **stats})

        return result_data

    @staticmethod
    def _calculate_speed_from_events(req_event_df, event_filter, time_logic_func):
        """
        通用的生成速度计算函数

        Args:
            req_event_df: 事件数据框
            event_filter: 用于筛选事件的函数
            time_logic_func: 用于计算时间差和速度的函数
        """
        if req_event_df.empty:
            logger.warning("req_event_df is empty")
            return []

        # 筛选事件
        filtered_events = req_event_df[event_filter(req_event_df)]

        # 按 rid 分组处理
        grouped = filtered_events.groupby('rid')
        speed_data = []

        for rid, group in grouped:
            # 按 start_time 排序
            group = group.sort_values('start_time').reset_index(drop=True)

            # 调用具体的时间逻辑函数计算速度
            group_speed_data = time_logic_func(group, rid)
            speed_data.extend(group_speed_data)

        logger.debug(f"Final speed_data length: {len(speed_data)}")
        return speed_data

    @staticmethod
    def _calculate_prefill_speed_logic(group, rid):
        """预填充速度计算逻辑"""
        speed_data = []

        # 查找 BatchSchedule (iter=0)
        batch_schedule_mask = (group['event'] == 'BatchSchedule') & (group['iter'] == 0)
        if not batch_schedule_mask.any():
            return speed_data

        batch_schedule_row = group[batch_schedule_mask].iloc[0]
        batch_start_time = batch_schedule_row['start_time']

        # 使用 batch_size 列获取批次大小
        num_tokens = batch_schedule_row.get('batch_size', 0)
        if pd.isna(num_tokens) or num_tokens <= 0:
            return speed_data

        # 查找第一个 Execute (iter=0)
        execute_mask = (group['event'] == 'Execute') & (group['iter'] == 0)
        if not execute_mask.any():
            return speed_data

        first_execute_row = group[execute_mask].iloc[0]
        execute_end_time = first_execute_row['end_time']

        # 计算时间差（微秒）
        time_diff_us = execute_end_time - batch_start_time

        # 计算生成速度（tokens/秒）
        if time_diff_us > 0 and num_tokens > 0:
            prefill_speed = num_tokens / (time_diff_us / 1000000.0)  # 转换为 tokens/秒
            speed_data.append({
                'timestamp_numeric': batch_start_time,
                'prefill_gen_speed': prefill_speed
            })

        return speed_data

    @staticmethod
    def _calculate_decode_speed_logic(group, rid):
        """解码速度计算逻辑"""
        speed_data = []

        # 计算相邻 Execute 之间的时间差
        for i in range(1, len(group)):
            current_row = group.iloc[i]
            prev_row = group.iloc[i - 1]

            # 只计算连续的 iter
            if current_row['iter'] != prev_row['iter'] + 1:
                continue

            # 使用当前行的 batch_size 获取批次大小
            num_tokens = current_row.get('batch_size', 0)
            if pd.isna(num_tokens) or num_tokens <= 0:
                continue

            # 计算时间差（微秒）
            time_diff_us = current_row['end_time'] - prev_row['end_time']

            # 计算生成速度（tokens/秒）
            if time_diff_us > 0:
                decode_speed = num_tokens / (time_diff_us / 1000000.0)  # 转换为 tokens/秒
                speed_data.append({
                    'timestamp_numeric': current_row['start_time'],
                    'decode_gen_speed': decode_speed
                })

        return speed_data

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
        prefill_gen_speed_views = ExporterLatency.gen_exporter_prefill_gen_speed_views(
            data.get("req_event_df", pd.DataFrame()))
        decode_gen_speed_views = ExporterLatency.gen_exporter_decode_gen_speed_views(
            data.get("req_event_df", pd.DataFrame()))

        write_result_to_db(TableConfig(table_name="prefill_gen_speed"), pd.DataFrame(prefill_gen_speed_views),
                           CREATE_PREFILL_GEN_SPEED_CURVE_VIEW_CONFIG)
        write_result_to_db(TableConfig(table_name="first_token_latency"), pd.DataFrame(first_token_latency_views),
                           CREATE_FIRST_TOKEN_LATENCY_CURVE_VIEW_CONFIG)
        write_result_to_db(TableConfig(table_name="req_latency"), pd.DataFrame(req_latency_views),
                           CREATE_REQUEST_LATENCY_CURVE_CONFIG)
        write_result_to_db(TableConfig(table_name="decode_gen_speed"), pd.DataFrame(decode_gen_speed_views),
                           CREATE_DECODE_GEN_SPEED_CURVE_VIEW_CONFIG)


PREFILL_GEN_SPEED_CURVE_VIEW_NAME = "Prefill_Generate_Speed_Latency_curve"
REQUEST_LATENCY_CURVE_VIEW_NAME = "Request_Latency_curve"
DECODE_GEN_SPEED_CURVE_VIEW_NAME = "Decode_Generate_Speed_Latency_curve"
FIRST_TOKEN_LATENCY_CURVE_VIEW_NAME = "First_Token_Latency_curve"

CREATE_PREFILL_GEN_SPEED_VIEW_SQL = f"""
    CREATE VIEW {PREFILL_GEN_SPEED_CURVE_VIEW_NAME} AS
    WITH converted AS (
        SELECT
            substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS datetime,
            avg, p99, p90, p50
    FROM
        prefill_gen_speed
    )
    SELECT
        datetime as time,
        round(cast(avg as REAL), 4) as "avg(tokens/s)",
        round(cast(p99 as REAL), 4) as "p99(tokens/s)", 
        round(cast(p90 as REAL), 4) as "p90(tokens/s)",
        round(cast(p50 as REAL), 4) as "p50(tokens/s)"
    FROM
        converted
    ORDER BY
        datetime ASC
"""

CREATE_REQUEST_LATENCY_SQL = f"""
    CREATE VIEW {REQUEST_LATENCY_CURVE_VIEW_NAME} AS
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
        round(cast(avg as REAL)/1000, 4) as "avg(ms)",
        round(cast(p99 as REAL)/1000, 4) as "p99(ms)",
        round(cast(p90 as REAL)/1000, 4) as "p90(ms)",
        round(cast(p50 as REAL)/1000, 4) as "p50(ms)"
    FROM
        converted
    ORDER BY
        datetime ASC
"""

CREATE_DECODE_GEN_SPEED_SQL = f"""
    CREATE VIEW {DECODE_GEN_SPEED_CURVE_VIEW_NAME} AS
    WITH converted AS (
        SELECT
            substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS datetime,
            avg, p99, p90, p50
    FROM
        decode_gen_speed
    )
    SELECT
        datetime as time,
        round(cast(avg as REAL), 4) as "avg(tokens/s)",
        round(cast(p99 as REAL), 4) as "p99(tokens/s)", 
        round(cast(p90 as REAL), 4) as "p90(tokens/s)",
        round(cast(p50 as REAL), 4) as "p50(tokens/s)"
    FROM
        converted
    ORDER BY
        datetime ASC
"""

CREATE_FIRST_TOKEN_LATENCY_SQL = f"""
    CREATE VIEW {FIRST_TOKEN_LATENCY_CURVE_VIEW_NAME} AS
    WITH converted AS (
        SELECT
            substr(timestamp, 1, 10) || ' ' || substr(timestamp, 12, 8) || '.' || substr(timestamp, 21, 6) AS datetime,
            p99, p90, p50, min_value
        FROM
            first_token_latency
    )
    SELECT
        datetime as time,
        cast(p99 as REAL) as "p99(ms)",
        cast(p90 as REAL) as "p90(ms)",
        cast(p50 as REAL) as "p50(ms)",
        cast(min_value as REAL) as "min(ms)"
    FROM
        converted
    ORDER BY
        datetime ASC
"""

CREATE_PREFILL_GEN_SPEED_CURVE_VIEW_CONFIG = CurveViewConfig(
    view_name=PREFILL_GEN_SPEED_CURVE_VIEW_NAME,
    sql=CREATE_PREFILL_GEN_SPEED_VIEW_SQL,
    description={
        "en": "Prefill Phase Token Throughput (tokens/s) Over Time For All Requests",
        "zh": "所有请求prefill阶段，不同时刻吞吐的token平均时延随时间变化折线图"
    }
)
CREATE_REQUEST_LATENCY_CURVE_CONFIG = CurveViewConfig(
    view_name=REQUEST_LATENCY_CURVE_VIEW_NAME,
    sql=CREATE_REQUEST_LATENCY_SQL,
    description={
        "en": "End-to-End Latency Over Time For All Requests",
        "zh": "所有请求端到端时延随时间变化折线图"
    }
)
CREATE_DECODE_GEN_SPEED_CURVE_VIEW_CONFIG = CurveViewConfig(
    view_name=DECODE_GEN_SPEED_CURVE_VIEW_NAME,
    sql=CREATE_DECODE_GEN_SPEED_SQL,
    description={
        "en": "Decode Phase Token Throughput (tokens/s) Over Time For All Requests",
        "zh": "所有请求decode阶段，不同时刻吞吐的token平均时延随时间变化折线图"
    }
)
CREATE_FIRST_TOKEN_LATENCY_CURVE_VIEW_CONFIG = CurveViewConfig(
    view_name=FIRST_TOKEN_LATENCY_CURVE_VIEW_NAME,
    sql=CREATE_FIRST_TOKEN_LATENCY_SQL,
    description={
        "en": "Time to First Token (TTFT) Over Time For All Requests",
        "zh": "所有请求首token时延随时间变化折线图"
    }
)