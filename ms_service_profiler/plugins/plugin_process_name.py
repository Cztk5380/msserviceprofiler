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
        tx_data_df: pd.DataFrame = data.get('tx_data_df')
        
        if 'scope#dp' not in tx_data_df or 'rid' not in tx_data_df:
            # nothing to do
            return data

        # 从kvcache 中获取 rid 和 dp 的键值对
        kvcache_df = tx_data_df[tx_data_df['domain'] == 'KVCache']
        kvcache_df = kvcache_df.drop_duplicates(subset='rid', keep='first')
        rid_dp_df = kvcache_df[['scope#dp', 'rid']]
        rid_dp_dict = rid_dp_df.set_index('rid')['scope#dp'].to_dict()

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

        # 处理 dpRankId 逻辑
        pid_label_map = cls.process_dp_rank_id(tx_data_df, pid_label_map)

        # 查找所有的 preprocess 标签，这里面有 rid ，获取第一个 rid ，从键值对中查找 dp ，组成 pid 到 dp 的键值对
        preprocess_df = tx_data_df[tx_data_df['name'] == 'preprocess']
        preprocess_df = preprocess_df.drop_duplicates(subset='pid', keep='first')

        for row in preprocess_df.itertuples():
            rid_list = row.rid_list if row.rid_list is not None else []
            for rid in rid_list:
                dp = rid_dp_dict.get(rid)
                if dp is not None:
                    pid_label_map.setdefault(row.pid, dict())
                    pid_label_map[row.pid]['dp'] = dp
                    break

        logger.debug(str(pid_label_map))
        data['pid_label_map'] = pid_label_map
        return data

    @classmethod
    def process_dp_rank_id(cls, tx_data_df: pd.DataFrame, pid_label_map: dict) -> dict:
        """
        处理 dpRankId 逻辑，将结果更新到 pid_label_map 中
        """
        if 'dpRankId' not in tx_data_df.columns:
            return pid_label_map

        valid_dp_rank_df = tx_data_df[['dpRankId', 'pid']].drop_duplicates()
        valid_dp_rank_df = valid_dp_rank_df[
            valid_dp_rank_df['dpRankId'].notna() &
            (valid_dp_rank_df['dpRankId'] != -1)
            ]

        if not valid_dp_rank_df.empty:
            # 使用 groupby 和 transform 找到每个 dpRankId 对应的第一个 pid
            first_pid = valid_dp_rank_df.groupby('dpRankId')['pid'].transform('first')
            valid_dp_rank_df = valid_dp_rank_df.drop_duplicates('dpRankId')
            valid_dp_rank_df['first_pid'] = first_pid

            # 创建 dp_rank_pid_map
            dp_rank_pid_map = dict(zip(valid_dp_rank_df['dpRankId'], valid_dp_rank_df['first_pid']))

            # 更新 pid_label_map
            for dp_rank, pid in dp_rank_pid_map.items():
                if pid in pid_label_map:
                    pid_label_map[pid]['dp_rank'] = str(dp_rank)
                else:
                    pid_label_map[pid] = {'dp_rank': str(dp_rank)}

        return pid_label_map
