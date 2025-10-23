# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import ast
from collections import defaultdict

import numpy as np
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import (
    write_result_to_csv, write_result_to_db,
    check_domain_valid, CURVE_VIEW_NAME_LIST
)
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import key_except


def filter_batch_df(batch_name, batch_df):
    batch_df['batch_size'] = batch_df['batch_size'].astype(float)
    batch_df = batch_df[batch_df['name'].isin(['modelExec', batch_name])]
    ori_columns = ['name', 'res_list', 'start_time', 'end_time', 'batch_size', \
        'batch_type', 'during_time']
    existing_columns = [col for col in ori_columns if col in batch_df.columns]
    batch_df = batch_df[existing_columns]
    batch_df['during_time'] = batch_df['during_time'] / US_PER_MS
    batch_df['start_time'] = batch_df['start_time'] // US_PER_MS
    batch_df['end_time'] = batch_df['end_time'] // US_PER_MS
    return batch_df


def get_rename_cols(ori_cols):
    rename_cols = {
        'start_time': 'start_time(ms)', 'end_time': 'end_time(ms)',
        'during_time': 'during_time(ms)'
    }
    return rename_cols


class ExporterBatchData(ExporterBase):
    name = "batch_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.info)
    def parse_batch_exec_req(cls, batch_event_df: pd.DataFrame):
        """
        解析 batch 执行和请求数据
        """

        # 初始化
        batch_exec = pd.DataFrame(columns=["batch_id", "name", "pid", "start", "end"])
        batch_req = pd.DataFrame(columns=["batch_id", "req_id", "rid", "iter", "block"])

        try:
            if batch_event_df is None or batch_event_df.empty:
                return batch_exec, batch_req

            # 构建 batch_exec
            batch_exec = cls.build_batch_exec(batch_event_df)

            # 构建 batch_req
            batch_req = cls.build_batch_req(batch_event_df)

        except Exception as e:
            logger.error(f"parse_batch_exec_req error: {e}", exc_info=True)

        return batch_exec, batch_req

    @classmethod
    def build_batch_exec(cls, batch_event_df):
        """构建 batch_exec 数据"""
        batch_event_df_sorted = batch_event_df.sort_values("start_time").reset_index(drop=True)
        batch_event_df_sorted["logical_batch_id"] = (batch_event_df_sorted["event"] == "BatchSchedule").cumsum()

        all_logical_batch_ids = sorted(batch_event_df_sorted["logical_batch_id"].unique())
        logical_batch_to_batch_id = {
            lbid: idx + 1
            for idx, lbid in enumerate(all_logical_batch_ids)
        }

        batch_event_df_sorted["batch_id"] = batch_event_df_sorted["logical_batch_id"].map(logical_batch_to_batch_id)

        batch_exec = batch_event_df_sorted.groupby(["batch_id", "event", "pid"]).agg({
            "start_time": "min",
            "end_time": "max"
        }).reset_index()

        batch_exec = batch_exec.rename(columns={
            "start_time": "start",
            "end_time": "end"
        })

        return batch_exec.sort_values(["batch_id", "start"]).reset_index(drop=True)

    @classmethod
    def build_batch_req(cls, batch_event_df):
        """构建 batch_req 数据"""
        schedule_events = batch_event_df[batch_event_df["event"].isin(["BatchSchedule", "batchFrameworkProcessing"])]

        if schedule_events.empty:
            return pd.DataFrame(columns=["batch_id", "req_id", "rid", "iter", "block"])

        # 提取 schedule 数据
        schedule_data = cls.extract_schedule_data(schedule_events)

        if schedule_data.empty:
            return pd.DataFrame(columns=["batch_id", "req_id", "rid", "iter", "block"])

        # 排序
        sorted_data = cls.sort_schedule_data(schedule_data)

        # 添加 batch_id
        sorted_data["batch_id"] = range(1, len(sorted_data) + 1)

        # 处理 block 信息
        sorted_data["block"] = None
        if "blocks" in batch_event_df.columns:
            forward_mapping = cls.build_forward_mapping(batch_event_df)
            sorted_data["block"] = cls.assign_blocks_vectorized(sorted_data, forward_mapping)

        return sorted_data[["batch_id", "req_id", "rid", "iter", "block"]]

    @classmethod
    def extract_schedule_data(cls, schedule_events):
        """提取 schedule 事件数据"""
        all_data = []
        batch_id_values = schedule_events["batch_id"].values
        start_time_values = schedule_events["start_time"].values

        for i in range(len(schedule_events)):
            items = cls.safe_literal_eval(batch_id_values[i])
            sched_time = start_time_values[i]
            item_data = cls.extract_schedule_items(items, sched_time)
            all_data.extend(item_data)

        return pd.DataFrame(all_data) if all_data else pd.DataFrame()

    @classmethod
    def extract_schedule_items(cls, items, sched_time):
        """提取单个 schedule 事件中的 items"""
        if not isinstance(items, list):
            return []

        item_data = []
        for item in items:
            if not isinstance(item, dict):
                continue

            rid = item.get("rid")
            if rid is None:
                continue

            item_data.append({
                "req_id": item.get("req_id") or rid,
                "rid": rid,
                "iter": item.get("iter", 0),
                "schedule_time": sched_time
            })

        return item_data

    @staticmethod
    def sort_schedule_data(schedule_data):
        """排序 schedule 数据"""

        if schedule_data.empty:
            return schedule_data

        sort_indices = np.lexsort((
            schedule_data["iter"].values,
            pd.Series(schedule_data["req_id"]).fillna("").values
        ))
        return schedule_data.iloc[sort_indices].reset_index(drop=True)

    @classmethod
    def build_forward_mapping(cls, batch_event_df):
        """构建 forward 事件映射"""

        forward_events = batch_event_df[batch_event_df["event"] == "forward"]
        if forward_events.empty:
            return {}

        # 创建完整的映射结构
        forward_mapping = defaultdict(list)

        batch_id_values = forward_events["batch_id"].values
        blocks_values = forward_events.get("blocks", pd.Series([[]] * len(forward_events))).values
        start_time_values = forward_events["start_time"].values

        for i in range(len(forward_events)):
            items = cls.safe_literal_eval(batch_id_values[i])
            blocks = blocks_values[i] if i < len(blocks_values) else []
            fwd_time = float(start_time_values[i])

            forward_records = cls.create_forward_records(items, blocks, fwd_time)
            for record in forward_records:
                forward_mapping[record["rid"]].append({
                    "time": record["time"],
                    "blocks": record["blocks"]
                })

        # 为每个 rid 的记录按时间排序
        for rid in forward_mapping:
            forward_mapping[rid].sort(key=lambda x: x["time"])

        return forward_mapping

    @classmethod
    def create_forward_records(cls, items, blocks, fwd_time):
        """创建 forward 记录"""
        if not isinstance(items, list):
            return []

        records = []
        for item in items:
            if not isinstance(item, dict) or "rid" not in item:
                continue

            rid = str(item["rid"])
            records.append({
                "rid": rid,
                "time": fwd_time,
                "blocks": blocks if isinstance(blocks, list) else []
            })

        return records

    @classmethod
    def assign_blocks_vectorized(cls, schedule_data, forward_mapping):
        """高性能向量化 block 分配"""
        if schedule_data.empty:
            return []

        # 预先转换数据类型，避免重复转换
        rids = schedule_data["rid"].astype(str).values
        iters = schedule_data["iter"].values.astype(int)
        sched_times = schedule_data["schedule_time"].values.astype(float)

        blocks_result = [None] * len(schedule_data)

        # 批量处理
        for i in range(len(schedule_data)):
            rid = rids[i]
            iter_num = iters[i]
            sched_time = sched_times[i]

            if rid is None or rid not in forward_mapping:
                continue

            records = forward_mapping[rid]
            if not records:
                continue

            # 策略1: 时间 >= schedule_time
            block_value = cls.find_block_in_future(records, iter_num, sched_time)

            # 策略2: 时间 < schedule_time
            if block_value is None:
                block_value = cls.find_block_in_past(records, iter_num, sched_time)

            # 策略3: fallback
            if block_value is None:
                block_value = cls.find_block_fallback(records, iter_num)

            blocks_result[i] = block_value

        return blocks_result

    @classmethod
    def find_block_in_future(cls, records, iter_num, sched_time):
        """查找时间 >= schedule_time 的记录"""
        for record in records:
            if record["time"] < sched_time:
                continue

            blocks = record["blocks"]
            if not isinstance(blocks, list) or not blocks:
                continue

            return blocks[min(iter_num, len(blocks) - 1)]

        return None

    @classmethod
    def find_block_in_past(cls, records, iter_num, sched_time):
        """查找时间 < schedule_time 的记录（最近的）"""
        for record in reversed(records):
            if record["time"] >= sched_time:
                continue

            blocks = record["blocks"]
            if not isinstance(blocks, list) or not blocks:
                continue

            return blocks[min(iter_num, len(blocks) - 1)]

        return None

    @classmethod
    def find_block_fallback(cls, records, iter_num):
        """fallback 策略：使用最后一条记录"""
        if not records:
            return None

        last_record = records[-1]
        blocks = last_record["blocks"]

        if not isinstance(blocks, list) or not blocks:
            return None

        return blocks[min(iter_num, len(blocks) - 1)]

    @staticmethod
    def safe_literal_eval(x):
        """安全的字面量求值"""
        if pd.isna(x) or x is None:
            return []
        if isinstance(x, str):
            try:
                return ast.literal_eval(x)
            except (ValueError, SyntaxError):
                return []
        return x if isinstance(x, list) else []

    @classmethod
    @timer(logger.debug)
    @key_except('domain', 'name', ignore=True, msg="ignoring current exporter by default.")
    def export(cls, data) -> None:
        if 'csv' in cls.args.format or 'db' in cls.args.format:
            df = data.get('tx_data_df')
            if df is None:
                logger.warning("There is no service prof data, batch.csv will not be generated. Please check. ")
                return
            output = cls.args.output_path

            if check_domain_valid(df, ['ModelExecute', 'BatchSchedule', 'Schedule'], 'batch') is False:
                return

            # 获取组batch字段名称，旧版本为BatchScheduler，新版本为batchFrameworkProcessing
            if (df['name'] == 'BatchSchedule').any():
                batch_name = 'BatchSchedule'
            elif (df['name'] == 'batchFrameworkProcessing').any():
                batch_name = 'batchFrameworkProcessing'
            else:
                batch_name = 'Schedule'
            batch_df = df[df['name'].isin([batch_name, 'modelExec'])].copy()
            if batch_df.empty:
                logger.warning("No batch data found. batch.csv will not be generated. Please check ")
                return
            # 筛选显示
            batch_df = filter_batch_df(batch_name, batch_df)
            rename_cols = get_rename_cols(batch_df.columns)

            # 构建batch_req_df和batch_exec_df
            batch_event_df = data.get('batch_event_df')

            batch_exec_df, batch_req_df = cls.parse_batch_exec_req(batch_event_df)

            if 'db' in cls.args.format:
                df_param_list = [
                    [batch_df, 'batch'],
                    [batch_req_df, 'batch_req'],
                    [batch_exec_df, 'batch_exec']
                ]
                write_result_to_db(
                    df_param_list=df_param_list,
                    create_view_sql=[CREATE_BATCH_VIEW_SQL],
                    table_name='batch',
                    rename_cols=rename_cols
                )

            if 'csv' in cls.args.format:
                write_result_to_csv(batch_df, output, 'batch', rename_cols)



CREATE_BATCH_VIEW_SQL = f"""
    CREATE VIEW {CURVE_VIEW_NAME_LIST['batch']} AS
    WITH numbered_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY "start_time") - 1 AS batch_id,
            batch_size,
            batch_type
        FROM 
            batch
        WHERE 
            name in ('BatchSchedule', 'batchFrameworkProcessing')
    )
    SELECT
        batch_id,
        CASE
            WHEN batch_type = 'Prefill' THEN batch_size
            ELSE NULL
        END AS Prefill_batch_size,
        CASE
            WHEN batch_type = 'Decode' THEN batch_size
            ELSE NULL
        END AS Decode_batch_size
    FROM
        numbered_data
    ORDER BY
        batch_id;
"""