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
from enum import IntEnum, auto
import pandas as pd

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import KeyExcept


class HostRole(IntEnum):
    PREFILL = auto()
    DECODE = auto()
    OTHER = auto()


class BatchType(IntEnum):
    PREFILL = auto()
    DECODE = auto()
    MIX = auto()
    OTHER = auto()


class PluginTrace(PluginBase):
    name = "plugin_trace"
    depends = ["plugin_common", "plugin_req_status"]

    @staticmethod
    def map_batch_type(batch_type, batch_type_mapping):
        if pd.isna(batch_type):
            return None  # 保持为空值
        return batch_type_mapping.get(batch_type, "Other")

    @staticmethod
    def fix_batch_type(tx_data_df):
        with KeyExcept('name', 'hostname', 'pid', "batch_type", "rid_list", ignore=True, msg=""):
            # 创建映射字典
            batch_type_mapping = {
                0: "Prefill",
                1: "Decode",
                2: "Extend",
                3: "Mixed",
                5: "Dummy",
            }

            # MindIE重构后BatchSchedule中存在batchType字段，很准确，不需要执行之前逻辑
            if 'batchType' in tx_data_df.columns:
                # 使用映射方法设置 batch_type
                tx_data_df['batch_type'] = tx_data_df['batchType'].apply(
                    lambda x: PluginTrace.map_batch_type(x, batch_type_mapping)
                )
                # 跳过后续逻辑
                return tx_data_df

            # 判断每个进程的角色
            role_df = tx_data_df[tx_data_df["name"].isin(["prefillRes", "decodeRes"])]
            # role_map hostname+pid -> role
            role_map = dict(zip(zip(role_df['hostname'], role_df['pid']),
                                role_df['name'].map(dict(prefillRes=HostRole.PREFILL, decodeRes=HostRole.DECODE))))

            # 筛选出角色和 batch_type 冲突的部分
            tx_data_df['role'] = tx_data_df[tx_data_df['batch_type'].notna()].apply(
                lambda row: role_map.get((row['hostname'], row['pid']), None), axis=1)

            # prefill 冲突的部分，错判部分全部置为other
            prefill_conflict = tx_data_df[
                (tx_data_df['role'] == HostRole.PREFILL) & (tx_data_df['batch_type'] != "Prefill")]
            tx_data_df.loc[prefill_conflict.index, "batch_type"] = "Other"

            # decode 按请求拆分，最后一个置为decode，其他置为other, 再汇总为 batch，有一个为decode 就置为decode，其他置为 other
            decode_conflict = tx_data_df[
                (tx_data_df['role'] == HostRole.DECODE) & (tx_data_df['batch_type'] != "Decode")]
            decode_conflict = decode_conflict[["hostname", "pid", "name", "rid_list"]].reset_index().explode("rid_list")
            decode_conflict["batchtype"] = BatchType.OTHER
            last_rows = decode_conflict.groupby(["hostname", "pid", "name", "rid_list"]).tail(1).index
            decode_conflict.loc[last_rows, "batchtype"] = BatchType.DECODE
            str_batch_type_map = {
                BatchType.PREFILL: "Prefill",
                BatchType.DECODE: "Decode",
                BatchType.MIX: "Prefill, Decode",
                BatchType.OTHER: "Other",
            }
            decode_batch_type = decode_conflict.groupby("index")["batchtype"].min().map(str_batch_type_map)
            tx_data_df.loc[decode_batch_type.index, "batch_type"] = decode_batch_type

        return tx_data_df

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        with KeyExcept('token_id_list', 'batch_type', 'rid_list', ignore=True,
                       msg="ignoring current process by default."):
            tx_data_df = data.get('tx_data_df')
            if tx_data_df is None:
                return data

            # 解析batch，vllm数据解析modelexec自带batch_type字段
            if 'batch_type' not in tx_data_df.columns:
                tx_data_df['batch_type'] = None
            tx_data_df['batch_type'] = [
                extract_batch_type(token_list, batch_type)
                for token_list, batch_type in zip(tx_data_df['token_id_list'], tx_data_df['batch_type'])
            ]

            tx_data_df = PluginTrace.fix_batch_type(tx_data_df)

            tx_data_df['batch_size'] = [extract_batch_size(x) for x in tx_data_df['rid_list']]

            # PD混跑场景拆解batch size
            tx_data_df['prefill_batch_size'], tx_data_df['decode_batch_size'] = zip(
                *[
                    extract_batch_size_when_pd_mixed(token_list) if batch_type == 'Prefill, Decode' else (None, None)
                    for token_list, batch_type in zip(tx_data_df['token_id_list'], tx_data_df['batch_type'])
                ]
            )

            data['tx_data_df'] = tx_data_df
        return data


def extract_batch_type(token_list, batch_type):
    if batch_type is not None:
        return batch_type
    if token_list is None:
        return None
    has_prefill = 0 in token_list
    has_decode = any(x > 0 for x in token_list if x is not None)

    if has_prefill and has_decode:
        return 'Prefill, Decode'
    elif has_prefill and not has_decode:
        return 'Prefill'
    elif not has_prefill and has_decode:
        return 'Decode'
    else:
        return None


def extract_batch_size(rid_list):
    if rid_list is None:
        return None
    return str(int(len(rid_list)))


def extract_batch_size_when_pd_mixed(token_list):
    prefill_batch_size = token_list.count(0)
    decode_batch_size = len(token_list) - prefill_batch_size
    return prefill_batch_size, decode_batch_size

