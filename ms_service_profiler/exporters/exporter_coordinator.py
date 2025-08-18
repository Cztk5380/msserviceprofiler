# Copyright (c) 2025-2026 Huawei Technologies Co., Ltd.


from datetime import datetime
import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import (
    write_result_to_csv, write_result_to_db,
    check_domain_valid, CURVE_VIEW_NAME_LIST
)
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import key_except


class ExporterCoordinator(ExporterBase):
    name = "coordinator"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @timer(logger.info)
    @key_except('domain', 'name', ignore=True, msg="ignoring current exporter by default.")
    def export(cls, data) -> None:
        if "csv" not in cls.args.format and "db" not in cls.args.format:
            return

        df = data.get("tx_data_df")
        if df is None or df.empty:
            logger.warning("The data is empty or missing, please check")
            return

        if 'domain' not in df.columns or 'message' not in df.columns:
            logger.warning("Required columns 'domain' or 'message' not found.")
            return

        # Step 1: 筛选 domain == 'Coordinator'
        df_co = df[df['domain'] == 'Coordinator'].copy()

        if df_co.empty:
            logger.debug("No data with domain='Coordinator'")
            return

        # Step 2: 提取 message 中的字段到平铺列（方便处理）
        df_co = cls.extract_and_clean_message_fields(df_co)

        # 2.1. 构建事件时间线
        result_df = cls.build_prefill_decode_timeline(df_co)

        # 2.2 生成运行统计（add/end/running_count）
        stats_df = cls.build_running_request_stats(result_df, cls.safe_extract_minute)

        if stats_df.empty:
            logger.debug("No statistics generated.")
            return
        # 2.3. 补全时间线空缺
        stats_df = cls.complete_running_count_timeline(stats_df)

        if stats_df.empty:
            logger.debug("No statistics generated.")
            return

        # 2.4. 最终输出（可选：只保留需要的列）
        final_stats = stats_df[['time', 'address', 'node_type', 'add_count', 'end_count', 'running_count']]

        # Step 3: 导出结果
        cls.export_coordinator_data(final_stats)

    @classmethod
    def extract_and_clean_message_fields(cls, df):
        """
        从 DataFrame 的 'message' 字段中提取关键信息，并过滤无效数据。

        Args:
            df (pd.DataFrame): 包含 'message' 列的原始 DataFrame

        Returns:
            pd.DataFrame: 提取并清洗后的 DataFrame，包含 name, Phase, rid, PrefillAddress, DecodeAddress 字段
                          若 rid 缺失则被过滤，若结果为空返回空 DataFrame
        """

        def extract_message_field(msg, key):
            return msg.get(key) if isinstance(msg, dict) else None

        df_copy = df.copy()  # 避免修改原始数据

        fields = ['name', 'Phase', 'rid', 'PrefillAddress', 'DecodeAddress']
        for field in fields:
            df_copy[field] = df_copy['message'].apply(lambda x: extract_message_field(x, field))

        # rid 必须存在
        df_copy = df_copy.dropna(subset=['rid'])

        return df_copy

    @classmethod
    def build_prefill_decode_timeline(cls, events_df):
        """
        根据请求事件日志，构建 Prefill 和 Decode 阶段的关键事件时间线。

        对每个 rid，提取以下事件：
        - prefillStart: 来自 RequestDispatch 的 PrefillAddress
        - prefillEnd: 来自 GenerateToken 且 Phase=prefill（同时触发 decodeStart）
        - decodeStart: 与 prefillEnd 同一时刻，但发生在 DecodeAddress 上
        - decodeEnd: 来自 ReqFinish 事件，发生在 DecodeAddress 上

        Args:
            events_df (pd.DataFrame): 包含字段 ['rid', 'name', 'Phase', 'PrefillAddress',
                                       'DecodeAddress', 'start_datetime'] 的清洗后数据

        Returns:
            pd.DataFrame: 时间线记录，列包括：
                          ['rid', 'Address', 'start_datetime', 'prefillStart', 'decodeStart', 'prefillEnd', 'decodeEnd']
                          若无数据，返回空 DataFrame（带正确列）
        """
        from copy import copy

        def _create_timeline_record(base, address, timestamp, event_type):
            """辅助函数：创建一条带事件标记的记录"""
            record = copy(base)
            record['address'] = address
            record['start_datetime'] = timestamp
            # 所有可能的事件类型
            for key in ['prefillStart', 'decodeStart', 'prefillEnd', 'decodeEnd']:
                record[key] = True if key == event_type else None
            return record

        result_records = []

        for rid, group in events_df.groupby('rid'):
            record_base = {'rid': rid}

            # 提取 Prefill 和 Decode 地址（来自 RequestDispatch）
            dispatch_row = group[group['name'] == 'RequestDispatch']
            prefill_address = None
            decode_address = None
            if not dispatch_row.empty:
                msg = dispatch_row.iloc[0]
                prefill_address = msg['PrefillAddress']
                decode_address = msg['DecodeAddress']

            # === 1. prefillStart: RequestDispatch -> PrefillAddress ===
            if not dispatch_row.empty and prefill_address:
                row = dispatch_row.iloc[0]
                record = _create_timeline_record(
                    record_base,
                    address=prefill_address,
                    timestamp=row['start_datetime'],
                    event_type='prefillStart'
                )
                result_records.append(record)

            # === 2. prefillEnd: GenerateToken & Phase=prefill -> PrefillAddress ===
            prefill_row = group[
                (group['name'] == 'GenerateToken') &
                (group['Phase'].astype(str).str.lower() == 'prefill')
                ]
            if not prefill_row.empty and prefill_address:
                row = prefill_row.iloc[0]
                # prefillEnd 事件
                result_records.append(_create_timeline_record(
                    record_base,
                    address=prefill_address,
                    timestamp=row['start_datetime'],
                    event_type='prefillEnd'
                ))
                # decodeStart 事件（同一时间点，但发生在 decode 节点）
                if decode_address:
                    result_records.append(_create_timeline_record(
                        record_base,
                        address=decode_address,
                        timestamp=row['start_datetime'],
                        event_type='decodeStart'
                    ))

            # === 3. decodeEnd: ReqFinish -> DecodeAddress ===
            finish_row = group[group['name'].astype(str).str.lower() == 'Reqfinish']
            if not finish_row.empty and decode_address:
                row = finish_row.iloc[0]
                result_records.append(_create_timeline_record(
                    record_base,
                    address=decode_address,
                    timestamp=row['start_datetime'],
                    event_type='decodeEnd'
                ))

        # 构造最终 DataFrame
        if not result_records:
            # 返回空 DataFrame，但列结构正确
            columns = ['rid', 'address', 'start_datetime', 'prefillStart', 'decodeStart', 'prefillEnd', 'decodeEnd']
            return pd.DataFrame(columns=columns)

        result_df = pd.DataFrame(result_records)
        # 确保列顺序
        final_columns = ['rid', 'address', 'start_datetime', 'prefillStart', 'decodeStart', 'prefillEnd', 'decodeEnd']
        return result_df.reindex(columns=[col for col in final_columns if col in result_df.columns])

    @classmethod
    def safe_extract_minute(cls, dt, interval=5):
        try:
            dt_str = str(dt).strip()
            parsed = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S:%f')
            base_second = (parsed.second // interval) * interval

            # 构造新时间（清空秒以下，秒设为 base_second）
            truncated = parsed.replace(second=base_second, microsecond=0)

            # 返回字符串格式
            return truncated.strftime('%Y-%m-%d %H:%M:%S')  # 输出如 '2025-08-14 16:06:00'
        except Exception as e:
            logger.debug(f"Failed to parse datetime: {dt_str}, error: {e}")
            return None

    @classmethod
    def build_running_request_stats(cls, timeline_df, extract_minute_func):
        """
        根据事件时间线，统计每个时间片（分钟）每个节点（prefill/decode）的运行中请求数。

        Args:
            timeline_df (pd.DataFrame): 来自 build_prefill_decode_timeline 的输出，
                                       包含 ['address', 'start_datetime', 'prefillStart', 'decodeStart', ...]
            extract_minute_func (callable): 从 datetime 提取分钟级时间的函数，如 lambda dt: dt.floor('Min')

        Returns:
            pd.DataFrame: 包含以下列：
                          ['time', 'address', 'node_type', 'add_count', 'end_count', 'running_count']
                          若无有效数据，返回空 DataFrame
        """

        if timeline_df.empty:
            logger.debug("No data to generate statistics.")
            return pd.DataFrame(columns=['time', 'address', 'node_type', 'add_count', 'end_count', 'running_count'])

        # 添加分钟级时间列
        timeline_df = timeline_df.copy()
        timeline_df['time'] = timeline_df['start_datetime'].apply(extract_minute_func)
        valid_df = timeline_df.dropna(subset=['time'])

        if valid_df.empty:
            logger.debug("No valid 'time' field for statistics.")
            return pd.DataFrame(columns=['time', 'address', 'node_type', 'add_count', 'end_count', 'running_count'])

        # 构建事件列表
        event_list = []

        for _, row in valid_df.iterrows():
            addr = row['address']
            time = row['time']

            # 验证 address 有效性
            if not isinstance(addr, str) or not addr.strip():
                continue

            # 收集所有有效事件
            if pd.notna(row.get('prefillStart')) and row['prefillStart'] is True:
                event_list.append({'time': time, 'address': addr, 'node_type': 'prefill', 'event': 'start'})
            if pd.notna(row.get('prefillEnd')) and row['prefillEnd'] is True:
                event_list.append({'time': time, 'address': addr, 'node_type': 'prefill', 'event': 'end'})
            if pd.notna(row.get('decodeStart')) and row['decodeStart'] is True:
                event_list.append({'time': time, 'address': addr, 'node_type': 'decode', 'event': 'start'})
            if pd.notna(row.get('decodeEnd')) and row['decodeEnd'] is True:
                event_list.append({'time': time, 'address': addr, 'node_type': 'decode', 'event': 'end'})

        if not event_list:
            logger.debug("No events generated for statistics.")
            return pd.DataFrame(columns=['time', 'address', 'node_type', 'add_count', 'end_count', 'running_count'])

        events_df = pd.DataFrame(event_list)

        # 聚合：按 time, address, node_type 统计 start/end 数量
        stats = events_df.groupby(['time', 'address', 'node_type'], as_index=False).agg(
            add_count=('event', lambda x: (x == 'start').sum()),
            end_count=('event', lambda x: (x == 'end').sum())
        )

        # 确保按 address 和 node_type 排序，以便 running_count 累积正确
        stats = stats.sort_values(['address', 'node_type', 'time']).reset_index(drop=True)

        # 计算 running_count（累积运行中请求数）
        current_counts = {}
        running_counts = []

        for _, row in stats.iterrows():
            key = (row['address'], row['node_type'])
            net_change = row['add_count'] - row['end_count']
            current_count = current_counts.get(key, 0) + net_change
            current_count = max(0, current_count)  # 防止负数
            current_counts[key] = current_count
            running_counts.append(current_count)

        stats['running_count'] = running_counts

        return stats

    @classmethod
    def complete_running_count_timeline(cls, stats_df):
        """
        补全运行中请求数时间线的缺失时间点。

        对每个 (address, node_type) 组合：
        - 从其首次出现的时间点（first_time）开始；
        - 到所有数据中最晚的时间点结束；
        - 确保每个时间片都有记录，缺失的补为 0。

        Args:
            stats_df (pd.DataFrame): 包含 ['time', 'address', 'node_type', 'add_count', 'end_count', 'running_count']
                                     的统计结果，已按时间排序。

        Returns:
            pd.DataFrame: 补全后的时间线数据，按 ['time', 'address', 'node_type'] 排序。
                          若输入为空，返回空 DataFrame。
        """

        if stats_df.empty:
            return stats_df  # 保持列结构

        # 1. 数据清洗
        df = stats_df.copy()
        df['address'] = df['address'].astype(str).str.strip()
        df['node_type'] = df['node_type'].astype(str).str.strip()

        # 2. 去重：确保 (time, address, node_type) 唯一
        df = df.drop_duplicates(subset=['time', 'address', 'node_type'])

        # 3. 获取所有时间点（排序）
        all_times = sorted(df['time'].unique())

        if not all_times:
            return pd.DataFrame(columns=df.columns)

        # 4. 获取所有唯一的 (address, node_type) 组合
        node_groups = df[['address', 'node_type']].drop_duplicates()

        complete_rows = []

        # 5. 遍历每个节点组合
        for _, group in node_groups.iterrows():
            addr = group['address']
            ntype = group['node_type']

            # 获取该节点的所有数据
            node_data = df[(df['address'] == addr) & (df['node_type'] == ntype)]
            first_time = node_data['time'].min()
            # 所有 >= first_time 的时间点
            relevant_times = [t for t in all_times if t >= first_time]

            for t in relevant_times:
                existing = node_data[node_data['time'] == t]
                if not existing.empty:
                    record = existing.iloc[0].to_dict()
                else:
                    record = {
                        'time': t,
                        'address': addr,
                        'node_type': ntype,
                        'add_count': 0,
                        'end_count': 0,
                        'running_count': 0
                    }
                complete_rows.append(record)

        # 6. 构造完整 DataFrame
        completed_df = pd.DataFrame(complete_rows)

        # 7. 排序
        completed_df = completed_df.sort_values(['time', 'address', 'node_type']).reset_index(drop=True)

        return completed_df

    @classmethod
    def generate_coordinator_view_sql(cls, stats, view_name="v_coordinator_add_curve"):
        """
        根据当前 stats 数据，动态生成 coordinator 曲线视图 SQL
        """
        # 提取所有唯一的 (node_type, address) 组合
        nodes = stats[['node_type', 'address']].drop_duplicates().sort_values(['node_type', 'address'])

        # 生成每个节点的 CASE WHEN 列
        columns = []
        for _, row in nodes.iterrows():
            node_type = row['node_type']
            addr = row['address']
            col_alias = f"{node_type} {addr}"
            clause = f"""    MAX(CASE WHEN node_type = '{node_type}' AND address = '{addr}' 
            THEN add_count ELSE NULL END) AS "{col_alias}\""""
            columns.append(clause)

        # 拼接 SQL
        columns_sql = ",\n".join(columns)

        sql = f'''CREATE VIEW {view_name} AS
    SELECT
        time,
    {columns_sql}
    FROM
        coordinator
    GROUP BY
        time
    ORDER BY
        time;'''

        return sql

    @classmethod
    def export_coordinator_data(cls, final_stats):
        """
        将 coordinator 数据导出到 DB 或 CSV（根据 self.args.format）
        """
        if 'db' in cls.args.format:
            df_param_list = [
                [final_stats, 'coordinator']
            ]

            view_sql = cls.generate_coordinator_view_sql(
                final_stats,
                CURVE_VIEW_NAME_LIST['coordinator']
            )

            write_result_to_db(
                df_param_list=df_param_list,
                create_view_sql=[view_sql],
                table_name='coordinator',
            )

        if 'csv' in cls.args.format:
            write_result_to_csv(
                final_stats,
                cls.args.output_path,  # 假设 output 是实例属性
                'coordinator',
                {}
            )