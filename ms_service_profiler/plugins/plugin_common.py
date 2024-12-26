# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import json
import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase


class PluginCommon(PluginBase):
    name = "plugin_common"
    depends = ["plugin_concat"]

    @classmethod
    def parse(cls, data):
        tx_data_df = data.get("tx_data_df")
        if tx_data_df is None:
            raise ValueError("tx_data_df is None")

        tx_data_df = parse_message(tx_data_df)

        data["tx_data_df"] = tx_data_df
        return data


def extract_ids_from_reslist(rid_from_message, rid_map):
    res_list = rid_from_message
    rid = []
    token_id = []
    if res_list:
        for req in res_list:
            if isinstance(req, int):
                rid.append(req)
                continue
            elif isinstance(req, dict):
                rid.append(rid_map.get(req.get('rid', None), req.get('rid', None)))
            token_id.append(req.get('iter', None))
        return rid, token_id
    return res_list, res_list


def convert_message_to_json(message):
    if message.startswith('{') and message.endswith('}'):
        return json.loads(message)
    else:
        message = '{' + message[:-1] + '}'
        return json.loads(message)   


def extract_batch_type(token_list):
    if token_list is None:
        return None
    if all(token == 0 for token in token_list):
        return 'Prefill'
    elif 0 in token_list and len(set(token_list)) > 1:
        return 'Prefill, Decode'
    else:
        return 'Decode'


def extract_rid(rid_from_message, rid_map):
    rid, rid_list, token_id_list, batch_size = None, None, None, None
    if rid_from_message is not None:
        if isinstance(rid_from_message, int):
            rid = rid_from_message
        elif isinstance(rid_from_message, str):
            rid = str(rid_map.get(rid_from_message, rid_from_message))
        elif isinstance(rid_from_message, list):
            rid_list, token_id_list = extract_ids_from_reslist(rid_from_message, rid_map)
            rid = ','.join([str(x) for x in rid_list])
            batch_size = len(rid_list)
    return rid, rid_list, token_id_list, batch_size


def parse_rid(all_data_df):
    rid_link_map = {x.get("from"): x.get("to") for x in all_data_df[all_data_df["type"] == 3]["message"]}
    all_data_df['res_list'] = all_data_df['rid']
    all_data_df[['rid', 'rid_list', 'token_id_list', 'batch_size']] = all_data_df['rid'].apply(
        lambda x: extract_rid(x, rid_link_map)).apply(pd.Series)
    all_data_df = all_data_df.replace(to_replace=np.nan, value=None)
    all_data_df['batch_type'] = all_data_df['token_id_list'].apply(lambda x: extract_batch_type(x))
    return all_data_df


def parse_message(all_data_df):
    all_data_df['message'] = all_data_df['message'].apply(lambda x: convert_message_to_json(x))
    all_data_df = all_data_df.join(all_data_df['message'].apply(pd.Series))
    all_data_df = parse_rid(all_data_df)
    
    return all_data_df
