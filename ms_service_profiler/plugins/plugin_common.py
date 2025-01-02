# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import json
import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import ParseError, DataFrameMissingError, KeyMissingError, ValidationError


class PluginCommon(PluginBase):
    name = "plugin_common"
    depends = ["plugin_concat"]

    @classmethod
    def parse(cls, data):
        tx_data_df = data.get("tx_data_df")
        if tx_data_df is None:
            raise DataFrameMissingError("tx_data_df")

        tx_data_df = tx_data_df.replace(to_replace=np.nan, value=None)
        rid_link_map = parse_rid_map(tx_data_df)
        tx_data_df = parse_rid(tx_data_df, rid_link_map)

        data["tx_data_df"] = tx_data_df
        data["rid_link_map"] = rid_link_map

        check_columns_exist(
            tx_data_df,
            'name', 'type', 'rid', 'start_time', 'end_time', 'start_datetime', 'end_datetime', 'during_time'
            )
        return data


def extract_ids_from_reslist(rid_from_message, rid_map):
    if not rid_from_message:
        return [], []

    rid = []
    token_id = []

    for req in rid_from_message:
        if isinstance(req, int) or isinstance(req, float):
            rid.append(req)
            token_id.append(None)
        elif isinstance(req, dict):
            rid.append(rid_map.get(req.get('rid', None), req.get('rid', None)))
            token_id.append(req.get('iter', None))

    return rid, token_id


def extract_rid(rid_from_message, rid_map):
    rid, rid_list, token_id_list = None, None, None
    if rid_from_message is not None:
        if isinstance(rid_from_message, str):
            rid = str(rid_map.get(rid_from_message, rid_from_message))
        elif isinstance(rid_from_message, list):
            rid_list, token_id_list = extract_ids_from_reslist(
                rid_from_message, rid_map)
            rid = ','.join(map(str, rid_list))
        else:
            rid = str(rid_from_message)

    return rid, rid_list, token_id_list


def check_columns_exist(df, *columns_required):
    missing = [key for key in columns_required if key not in df.columns]
    if missing:
        raise KeyMissingError(key=",".join(missing))


def parse_rid_map(all_data_df):
    check_columns_exist(all_data_df, "type")

    df = all_data_df[all_data_df["type"] == 3]

    if "from" in df.columns and "to" in df.columns:
        rid_link_map = dict(zip(df['from'], df['to']))
    else:
        rid_link_map = {}

    try:
        rid_link_map = {k: int(v) for k, v in rid_link_map.items()}
    except Exception as ex:
        logger.error(f'rid must be integer. {ex}')
        raise

    return rid_link_map


def parse_rid(all_data_df, rid_link_map=None):
    try:
        check_columns_exist(all_data_df, "type", "message", "rid")
        if not isinstance(all_data_df['message'].iloc[0], dict):
            raise ValidationError("Message must be a dict.")
    except Exception as ex:
        logger.error(f'Cannot parse rid. Skip it. {ex}')
        return all_data_df

    all_data_df['res_list'] = all_data_df['rid']

    if rid_link_map is None:
        rid_link_map = parse_rid_map(all_data_df)

    df = all_data_df['rid'].apply(lambda x: extract_rid(x, rid_link_map))
    all_data_df[['rid', 'rid_list', 'token_id_list']] = pd.DataFrame(df.tolist(), index=all_data_df.index)

    return all_data_df
