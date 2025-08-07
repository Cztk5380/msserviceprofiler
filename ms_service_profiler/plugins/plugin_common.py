# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.plugins.plugin_vllm_helper import VllmHelper
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import DataFrameMissingError
from ms_service_profiler.utils.timer import timer


class PluginCommon(PluginBase):
    name = "plugin_common"
    depends = ["plugin_concat"]

    @classmethod
    @timer(logger.info)
    def parse(cls, data):
        tx_data_df = data.get("tx_data_df")
        if tx_data_df is None:
            raise DataFrameMissingError("tx_data_df")

        tx_data_df = tx_data_df.replace(to_replace=np.nan, value=None)
        data["tx_data_df"], data["rid_link_map"] = parse_rid(tx_data_df)

        return data


# 只有vllm框架数据解析会走这部分流程，从batchSchdule中的iter_size中获取迭代信息
def extract_iter_from_batch(req):
    rid = req.get('rid')
    iter_size = req.get('iter_size')
    return VllmHelper.add_req_batch_iter(rid, iter_size)


def extract_ids_from_reslist(rid_from_message, rid_map):
    if not rid_from_message:
        return [], [], []

    rid = []
    token_id = []
    dp_id = []

    for req in rid_from_message:
        if isinstance(req, int) or isinstance(req, float):
            rid.append(get_real_rid(req, rid_map))
            token_id.append(None)
        elif isinstance(req, dict):
            rid.append(get_real_rid(req.get('rid'), rid_map))
            # iter_size 为vllm数据采集特有字段
            if req.get('iter_size'):
                token_id.append(extract_iter_from_batch(req))
            # dp域信息
            elif req.get('dp'):
                dp_id.append(req.get('dp', None))
            else:
                token_id.append(req.get('iter', None))
        elif isinstance(req, str):
            rid.append(req)
            token_id.append(None)

    return rid, token_id, dp_id


def get_real_rid(rid_from_message, rid_map):
    if rid_from_message is None:
        return rid_from_message

    format_rid = convert_to_format_str(rid_from_message)
    return rid_map.get(format_rid, format_rid)


def extract_rid(rid_from_message, rid_map):
    rid, rid_list, token_id_list, dp_list = None, None, None, None
    if rid_from_message is not None:
        if isinstance(rid_from_message, list):
            rid_list, token_id_list, dp_list = extract_ids_from_reslist(rid_from_message, rid_map)
            rid = ','.join(map(str, rid_list))
        else:
            rid = get_real_rid(rid_from_message, rid_map)

    return rid, rid_list, token_id_list, dp_list


def convert_to_format_str(x):
    try:
        return str(int(x))
    except Exception as ex:
        return x


def parse_rid_map(all_data_df):
    df = all_data_df[all_data_df["type"] == 3]  # already checked 'type' in all_data_df
    if "from" in df.columns and "to" in df.columns:
        rid_link_map = dict(zip(df['to'], df['from']))
    else:
        rid_link_map = {}

    rid_link_map = {convert_to_format_str(k): convert_to_format_str(v) for k, v in rid_link_map.items()}

    return rid_link_map


def convert_rid_to_str(item, rid_map=None):
    """
    转换函数：
    1. 统一rid为字符串
    2. 应用rid_link_map映射
    """
    if not isinstance(item, list) or not item:
        return item

    processed = []
    for elem in item:
        if isinstance(elem, dict) and 'rid' in elem:
            # 应用映射
            original_rid = elem.get('rid')
            mapped_rid = str(rid_map.get(original_rid, original_rid)) if rid_map else original_rid
            # 保留其他字段（如iter）
            new_elem = {**elem, 'rid': str(mapped_rid)}
            processed.append(new_elem)
        else:
            processed.append(elem)
    return processed


def parse_rid(tx_data_df):
    if "type" not in tx_data_df.columns or "rid" not in tx_data_df.columns:
        logger.warning('Missing columns "type" or "rid". Skip parsing')
        return tx_data_df, None

    # 1.生成映射rid_link_map
    rid_link_map = parse_rid_map(tx_data_df)

    # 2. 使用带映射的convert_rid_to_str生成res_list
    tx_data_df['res_list'] = tx_data_df['rid'].map(
        lambda x: convert_rid_to_str(x, rid_link_map)  # 传入映射字典
    )

    # 3. 后续处理保持不变
    df = tx_data_df['rid'].apply(lambda x: extract_rid(x, rid_link_map))
    tx_data_df[['rid', 'rid_list', 'token_id_list', 'dp_list']] = pd.DataFrame(df.tolist(), index=tx_data_df.index)

    return tx_data_df, rid_link_map
