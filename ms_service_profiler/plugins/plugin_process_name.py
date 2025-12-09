# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import pandas as pd
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.timer import timer


class PluginProcessName(PluginBase):
    name = "plugin_process_name"
    depends = ["plugin_common"]

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        if data.get("tx_data_df") is None:
            return data

        tx_data_df: pd.DataFrame = data.get('tx_data_df')

        # 检查必要的列是否存在
        if 'rid' not in tx_data_df.columns:
            # nothing to do
            return data

        pid_label_map = {}

        # pid, hostname, hostuid 能唯一确定一个进程，但是都拼接到pid 会很大。下面找到最小的能区分的集合，能少拼接就少拼接
        tx_data_pid_df = tx_data_df.drop_duplicates(subset=['pid', 'hostname', 'hostuid'], keep='first')
        pid_candidates = (set(), set())
        for row in tx_data_pid_df.itertuples():
            pid_candidates[0].add(row.pid)
            pid_candidates[1].add((row.pid, row.hostname))
            pid_label_map[row.pid] = dict(hostname=row.hostname)
        
        if len(pid_candidates[0]) == len(tx_data_pid_df):
            tx_data_df['pid'] = tx_data_df['pid']
        elif len(pid_candidates[1]) == len(tx_data_pid_df):
            tx_data_df['pid'] = tx_data_df['pid'].astype("str") + '-' + tx_data_df['hostname']
        else:
            tx_data_df['pid'] = tx_data_df['pid'].astype("str") + '-' + tx_data_df['hostname'] + '-' + tx_data_df[
                'hostuid']

        # 使用dpRankId来拼接
        pid_label_map = cls.process_dp_rank_id(tx_data_df, pid_label_map)

        data['pid_label_map'] = pid_label_map
        return data

    @classmethod
    def process_dp_rank_id(cls, tx_data_df: pd.DataFrame, pid_label_map: dict) -> dict:
        """
        处理 dpRankId 逻辑，将结果更新到 pid_label_map 中
        """
        if 'dpRankId' not in tx_data_df.columns:
            logger.warning("dpRankId column not found in dataframe")
            return pid_label_map

        # 筛选有效的 dpRankId 数据
        valid_dp_rank_df = tx_data_df[['dpRankId', 'pid']].drop_duplicates()
        valid_dp_rank_df = valid_dp_rank_df[
            valid_dp_rank_df['dpRankId'].notna() &
            (valid_dp_rank_df['dpRankId'] != -1)
            ]

        if not valid_dp_rank_df.empty:
            # 使用 groupby 找到每个 dpRankId 对应的第一个 pid
            dp_rank_pid_map = {}

            for dp_rank_id, group in valid_dp_rank_df.groupby('dpRankId'):
                first_pid = group['pid'].iloc[0]  # 取第一个pid
                dp_rank_pid_map[dp_rank_id] = first_pid

                # 更新 pid_label_map
                if first_pid in pid_label_map:
                    pid_label_map[first_pid]['dp_rank'] = str(dp_rank_id)
                else:
                    pid_label_map[first_pid] = {'dp_rank': str(dp_rank_id)}

            logger.info(f"dp_rank_pid_map contains {len(dp_rank_pid_map)} entries")
        else:
            logger.warning("No valid dpRankId data found")
        return pid_label_map
