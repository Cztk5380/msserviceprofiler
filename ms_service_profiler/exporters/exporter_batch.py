# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------
import ast
from collections import defaultdict
from collections import namedtuple

import numpy as np
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import (
    write_result_to_csv, write_result_to_db, TableConfig,
    check_domain_valid, CurveViewConfig
)
from ms_service_profiler.constant import US_PER_MS
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import key_except


def filter_batch_df(batch_name, batch_df, tx_data_df=None):
    if batch_df is None or batch_df.empty:
        return batch_df

    if 'batch_size' in batch_df.columns:
        batch_df = batch_df.copy()
        batch_df['batch_size'] = batch_df['batch_size'].astype(float)

    filtered_df = batch_df[batch_df['name'].isin(['modelExec', 'Execute', batch_name])].copy()

    # 新增：为 BatchSchedule 行匹配上层计算好的 KVCache 字段
    filtered_df = add_precomputed_kv_cache_fields(filtered_df, tx_data_df)

    base_columns = [
        'name', 'res_list', 'start_datetime', 'end_datetime', 'during_time',
        'batch_type', 'prof_id', 'batch_size',
        # 新增 KVCache 字段
        'total_blocks', 'used_blocks', 'free_blocks',
        'blocks_allocated', 'blocks_freed', 'kvcache_usage_rate'
    ]
    batch_columns = [col for col in base_columns if col in filtered_df.columns]

    join_columns = batch_columns + ['pid']
    existing_columns = [col for col in join_columns if col in filtered_df.columns]
    filtered_df = filtered_df[existing_columns]

    if 'during_time' in filtered_df.columns:
        filtered_df['during_time'] = filtered_df['during_time'] / US_PER_MS

    filtered_df = add_columns_for_batch_size_and_tokens(filtered_df)
    filtered_df = add_dp_rank_column(filtered_df, tx_data_df)

    if 'pid' in filtered_df.columns:
        filtered_df = filtered_df.drop(columns=['pid'])

    desired_order = [col for col in base_columns if col in filtered_df.columns]
    remaining_columns = [col for col in filtered_df.columns if col not in desired_order]
    filtered_df = filtered_df[desired_order + remaining_columns]

    return filtered_df


def _is_valid_input_data(batch_df, tx_data_df):
    """检查输入数据是否有效"""
    if batch_df is None:
        return False
    if batch_df.empty:
        return False
    if tx_data_df is None:
        return False
    if tx_data_df.empty:
        return False
    return True


def add_precomputed_kv_cache_fields(batch_df, tx_data_df):
    """
    为每个 BatchSchedule 行匹配上层计算好的 KVCache 字段
    匹配规则：找到与 BatchSchedule 同一 prof_id 且时间最接近的 KVCacheStatus 数据
    """
    if not _is_valid_input_data(batch_df, tx_data_df):
        logger.warning("Input data is empty: batch_df is None or empty: {}, tx_data_df is None or empty: {}".format(
            batch_df is None or batch_df.empty, tx_data_df is None or tx_data_df.empty))
        return batch_df

    # 初始化新列并获取批处理调度数据
    new_columns = ['total_blocks', 'used_blocks', 'free_blocks',
                   'blocks_allocated', 'blocks_freed', 'kvcache_usage_rate']
    batch_df = _initialize_columns(batch_df, new_columns)

    # 获取并验证 BatchSchedule 数据
    batch_schedule_mask, batch_count = _get_batch_schedule_info(batch_df)
    if batch_schedule_mask is None:
        return batch_df

    # 获取并验证 KVCacheStatus 数据
    available_kv_cols, filtered_tx_data = _get_kv_cache_data(tx_data_df, new_columns)
    if available_kv_cols is None:
        return batch_df

    # 按 prof_id 分组处理
    batch_schedules_grouped = batch_df[batch_schedule_mask].groupby('prof_id')
    filtered_tx_data_grouped = filtered_tx_data.groupby('prof_id')

    total_matched, total_unmatched = _process_prof_id_groups(
        batch_df, batch_schedules_grouped, filtered_tx_data_grouped, filtered_tx_data, new_columns
    )

    # 检查最终结果
    _log_final_results(batch_df, new_columns, total_matched, total_unmatched)

    return batch_df


def _initialize_columns(batch_df, new_columns):
    """初始化新列"""
    for col in new_columns:
        batch_df[col] = pd.NA
    return batch_df


def _get_batch_schedule_info(batch_df):
    """获取 BatchSchedule 信息"""
    batch_schedule_mask = batch_df['name'] == 'BatchSchedule'
    if not batch_schedule_mask.any():
        logger.warning("No BatchSchedule records found in batch_df")
        return None, None

    batch_count = batch_schedule_mask.sum()
    logger.debug(f"Found {batch_count} BatchSchedule records to process")
    return batch_schedule_mask, batch_count


def _get_kv_cache_data(tx_data_df, new_columns):
    """获取并验证 KVCacheStatus 数据"""
    available_kv_cols = [col for col in new_columns if col in tx_data_df.columns]
    logger.debug(f"Available KVCache columns in tx_data_df: {available_kv_cols}")

    if not available_kv_cols:
        logger.warning("No precomputed KVCache fields found in tx_data_df")
        return None, None

    kv_cache_mask = (
            (tx_data_df['name'] == 'KVCacheStatus') &
            (tx_data_df[available_kv_cols].notna().any(axis=1))
    )
    filtered_tx_data = tx_data_df[kv_cache_mask].copy()

    if filtered_tx_data.empty:
        logger.warning("No KVCacheStatus records with non-empty values found in tx_data_df")
        return None, None

    return available_kv_cols, filtered_tx_data


def _process_prof_id_groups(batch_df, batch_schedules_grouped, filtered_tx_data_grouped, filtered_tx_data, new_columns):
    """处理按 prof_id 分组的数据"""
    total_matched = 0
    total_unmatched = 0

    for prof_id, prof_batch_schedules in batch_schedules_grouped:
        if prof_id not in filtered_tx_data_grouped.groups:
            logger.debug(f"Prof_id {prof_id}: No KVCacheStatus records found")
            continue

        prof_kv_cache_data = filtered_tx_data_grouped.get_group(prof_id).sort_values('start_time')
        logger.debug(
            f"Prof_id {prof_id}: Found {len(prof_batch_schedules)} BatchSchedule "
            f"records and {len(prof_kv_cache_data)} KVCacheStatus records")

        # 向量化匹配
        batch_times = prof_batch_schedules['start_time'].values
        kv_times = prof_kv_cache_data['start_time'].values
        kv_cache_indices = prof_kv_cache_data.index

        matched, unmatched = _process_single_prof_id(
            batch_df, prof_batch_schedules, batch_times, kv_times, kv_cache_indices,
            filtered_tx_data, new_columns
        )
        total_matched += matched
        total_unmatched += unmatched

    return total_matched, total_unmatched


def _process_single_prof_id(batch_df, prof_batch_schedules, batch_times, kv_times, kv_cache_indices,
                           filtered_tx_data, new_columns):
    """处理单个 prof_id 的数据"""
    matched = 0
    unmatched = 0

    for i, batch_idx in enumerate(prof_batch_schedules.index):
        closest_idx = find_closest_kv_cache_idx(batch_times[i], kv_times, kv_cache_indices)
        if closest_idx is None:
            logger.debug(
                f"No matching KVCacheStatus data found for prof_id {prof_batch_schedules.name}, batch_idx {batch_idx}")
            unmatched += 1
            continue

        closest_row = filtered_tx_data.loc[closest_idx]
        match_type = "after" if closest_row['start_time'] >= batch_times[i] else "before"
        logger.debug(
            f"Matched BatchSchedule (idx={batch_idx}, time={batch_times[i]}) "
            f"with KVCacheStatus data (time={closest_row['start_time']}, match_type={match_type})")

        # 复制字段值
        _update_batch_row_with_kv_cache_data(batch_df, batch_idx, closest_row, new_columns)
        matched += 1

    return matched, unmatched


def _update_batch_row_with_kv_cache_data(batch_df, batch_idx, closest_row, new_columns):
    """更新 batch_df 中的行，添加 KVCache 数据"""
    for col in new_columns:
        if col in closest_row:
            original_value = closest_row[col]
            batch_df.at[batch_idx, col] = original_value
            logger.debug(f"  Setting {col} = {original_value} (type: {type(original_value)})")
            if original_value == 0 or pd.isna(original_value):
                logger.debug(f"  Warning: {col} is 0 or NaN, checking if field name is different")


def _log_final_results(batch_df, new_columns, total_matched, total_unmatched):
    """记录最终结果"""
    result_values = batch_df[new_columns].dropna(how='all')
    logger.debug(
        f"Successfully matched {total_matched} records, "
        f"{total_unmatched} unmatched, {len(result_values)} with KVCache fields")

    if not result_values.empty:
        for col in new_columns:
            non_null_count = result_values[col].notna().sum()
            if non_null_count > 0:
                non_zero_count = (result_values[col] != 0).sum()
                sample_values = result_values[col].dropna().head(3).tolist()
                logger.debug(
                    f"  {col}: {non_null_count} non-null values, "
                    f"{non_zero_count} non-zero values, samples: {sample_values}")
    else:
        logger.warning("No KVCache fields were successfully added")


def find_closest_kv_cache_idx(batch_time, kv_times, kv_cache_indices):
    """查找最接近的 KVCacheStatus 索引"""
    after_mask = kv_times >= batch_time
    if after_mask.any():
        return kv_cache_indices[after_mask][0]

    before_mask = kv_times < batch_time
    if before_mask.any():
        return kv_cache_indices[before_mask][-1]

    return None


def add_columns_for_batch_size_and_tokens(batch_df):
    """
    计算P_batch_size和D_batch_size
    计算本批次调度的total_scheduled_tokens，P_scheduled_tokens和D_scheduled_tokens
    """

    BatchResult = namedtuple('BatchResult', [
        'Prefill_batch_size',
        'Decode_batch_size',
        'Prefill_scheduled_tokens',
        'Decode_scheduled_tokens',
        'total_scheduled_tokens'
    ])

    def get_req_type(res_data):
        """获取请求类型：0为Prefill，1为Decode"""
        if "type" in res_data:
            return res_data.get("type", -1)
        else:
            # iter=0 对应 type=0 (Prefill), iter>0 对应 type=1 (Decode)
            return 0 if res_data.get("iter", -1) == 0 else 1

    def get_num_tokens(res_data):
        """获取token数量，支持多种字段名"""
        num_tokens = 0
        if "num_scheduled_tokens" in res_data:
            num_tokens = res_data.get("num_scheduled_tokens", 0)
        elif "num_scheduled_tokens=" in res_data:
            num_tokens = res_data.get("num_scheduled_tokens=", 0)

        # 如果获取到的 tokens 是字符串，尝试转换为数字
        if isinstance(num_tokens, str):
            try:
                num_tokens = float(num_tokens)
            except (ValueError, TypeError):
                num_tokens = 0
        return num_tokens

    def process_res_list(res_list):
        if not res_list or not isinstance(res_list, list):
            return BatchResult(0, 0, 0, 0, 0)

        p_count_batch_size = 0
        d_count_batch_size = 0
        p_scheduled_tokens = 0
        d_scheduled_tokens = 0

        try:
            for res_data in res_list:
                if not isinstance(res_data, dict):
                    continue

                req_type = get_req_type(res_data)
                num_tokens = get_num_tokens(res_data)

                if req_type == 0:
                    p_count_batch_size += 1
                    p_scheduled_tokens += num_tokens
                elif req_type == 1:
                    d_count_batch_size += 1
                    d_scheduled_tokens += num_tokens

            return BatchResult(
                p_count_batch_size, d_count_batch_size,
                p_scheduled_tokens, d_scheduled_tokens,
                p_scheduled_tokens + d_scheduled_tokens
            )

        except Exception as e:
            logger.warning(f"Invalid batch format: {e}")
            return BatchResult(0, 0, 0, 0, 0)

    results = batch_df['res_list'].apply(process_res_list)
    batch_df[['Prefill_batch_size', 'Decode_batch_size',
              'Prefill_scheduled_tokens', 'Decode_scheduled_tokens',
              'total_scheduled_tokens']] = pd.DataFrame(results.tolist(), index=batch_df.index)

    return batch_df


def add_dp_rank_column(batch_df, tx_data_df):
    """
    根据 tx_data_df 中 domain/name 都为 Meta 且 dpRankId 有值的数据，为 batch_df 添加 dp_rank 列
    """

    dp_rank_column = 'dp_rank'

    if batch_df is None:
        return batch_df

    if 'pid' not in batch_df.columns:
        batch_df[dp_rank_column] = pd.NA
        return batch_df

    if tx_data_df is None or tx_data_df.empty:
        batch_df[dp_rank_column] = pd.NA
        return batch_df

    required_columns = {'pid', 'dpRankId', 'domain', 'name'}
    if not required_columns.issubset(tx_data_df.columns):
        batch_df[dp_rank_column] = pd.NA
        return batch_df

    dp_rank_df = tx_data_df[
        (tx_data_df['domain'] == 'Meta') &
        (tx_data_df['name'] == 'Meta') &
        (tx_data_df['dpRankId'].notna())
    ][['pid', 'dpRankId']].drop_duplicates()

    if dp_rank_df.empty:
        batch_df[dp_rank_column] = pd.NA
        return batch_df

    dp_rank_df = dp_rank_df.rename(columns={'dpRankId': dp_rank_column})

    batch_df = batch_df.merge(dp_rank_df, how='left', on='pid')

    if dp_rank_column not in batch_df.columns:
        batch_df[dp_rank_column] = pd.NA

    return batch_df


class ExporterBatchData(ExporterBase):
    name = "batch_data"

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
            batch_df = df[df['name'].isin([batch_name, 'modelExec', 'Execute'])].copy()
            if batch_df.empty:
                logger.warning("No batch data found. batch.csv will not be generated. Please check ")
                return
            # 筛选显示
            batch_df = filter_batch_df(batch_name, batch_df, df)

            # 构建batch_req_df和batch_exec_df
            batch_event_df = data.get('batch_event_df')

            batch_exec_df, batch_req_df = cls.parse_batch_exec_req(batch_event_df)

            if 'db' in cls.args.format:
                write_result_to_db(CREATE_BATCH_TABLE_CONFIG, batch_df, CREATE_BATCH_VIEW_CONFIGS)
                write_result_to_db(TableConfig(table_name="batch_exec"), batch_exec_df)
                write_result_to_db(TableConfig(table_name="batch_req"), batch_req_df)

            if 'csv' in cls.args.format:
                write_result_to_csv(batch_df, output, 'batch', BATCH_RENAME_COLS)


BATCH_RENAME_COLS = {
    'start_datetime': 'start_time',
    'end_datetime': 'end_time',
    'during_time': 'during_time(ms)',
    'batch_size': 'total_batch_size',
}

CREATE_BATCH_TABLE_CONFIG = TableConfig(
    table_name="batch",
    create_view=True,
    view_name="batch_info",
    view_rename_cols=BATCH_RENAME_COLS,
    description={
        "en": "Servitized inference batch-level metrics: Batch Scheduling Latency and Batch Execution Latency",
        "zh": "服务化推理batch为粒度的详细数据，包含组batch和执行batch两种耗时信息"
    }
)

BATCH_SIZE_CURVE_VIEW_NAME = "Batch_Size_curve"
BATCH_TOKEN_CURVE_VIEW_NAME = "Batch_Token_curve"

CREATE_BATCH_SIZE_VIEW_SQL = f"""
    CREATE VIEW {BATCH_SIZE_CURVE_VIEW_NAME} AS
    WITH numbered_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY "start_datetime") - 1 AS batch_id,
            batch_size,
            Prefill_batch_size,
            Decode_batch_size
        FROM 
            batch
        WHERE 
            name in ('BatchSchedule', 'batchFrameworkProcessing')
    )
    SELECT
        batch_id,
        batch_size as total_batch_size,
        Prefill_batch_size,
        Decode_batch_size
    FROM
        numbered_data
    ORDER BY
        batch_id;
"""

CREATE_BATCH_TOKEN_VIEW_SQL = f"""
    CREATE VIEW {BATCH_TOKEN_CURVE_VIEW_NAME} AS
    WITH numbered_data AS (
        SELECT 
            ROW_NUMBER() OVER (ORDER BY "start_datetime") - 1 AS batch_id,
            total_scheduled_tokens,
            Prefill_scheduled_tokens,
            Decode_scheduled_tokens
        FROM 
            batch
        WHERE 
            name in ('BatchSchedule', 'batchFrameworkProcessing')
    )
    SELECT
        batch_id,
        total_scheduled_tokens,
        Prefill_scheduled_tokens,
        Decode_scheduled_tokens
    FROM
        numbered_data
    ORDER BY
        batch_id;
"""

CREATE_BATCH_VIEW_CONFIGS = [
    CurveViewConfig(
        view_name=BATCH_SIZE_CURVE_VIEW_NAME,
        sql=CREATE_BATCH_SIZE_VIEW_SQL,
        description={
            "en": "The number of requests per batch in the BatchSchedule process, sequenced by time "
                  "and segmented by prefill and decode phases",
            "zh": "BatchSchedule过程中每个batch包含的请求数量折线图，根据时间排序，区分prefill和decode"
        }
    ),
    CurveViewConfig(
        view_name=BATCH_TOKEN_CURVE_VIEW_NAME,
        sql=CREATE_BATCH_TOKEN_VIEW_SQL,
        description={
            "en": "Token counts in the BatchSchedule process: Total, Prefill, and Decode", 
            "zh": "BatchSchedule过程中的总token数，prefill占用token数，decode占用token数"
        }
    )
]