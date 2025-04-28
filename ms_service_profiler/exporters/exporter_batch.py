# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from enum import Enum
from pathlib import Path
import json
import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import save_dataframe_to_csv
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import add_table_into_visual_db

def is_contained_vaild_dp_batch_info(rid_list, dp_id_list):
    if rid_list is None or dp_id_list is None or len(rid_list) != len(dp_id_list):
        return False

    return True


def get_forward_df(df):
    forward_df = df[df['name'] == 'forward']

    df_list = forward_df.groupby('pid')
    forward_df_list = []
    for _, pre_df in df_list:
        forward_df_list.append(pre_df.reset_index(drop=True))

    if len(forward_df_list) <= 0:
        logger.warning("msproftx.db has no forward info, please check.")
        return None

    # 初始化一个字典来存储每行的最大time值及其对应的DataFrame索引
    max_forward_during_time = []

    for row_index in forward_df_list[0].index:  # 假设所有DataFrame的行索引相同
        max_during_time = -1
        max_df_index = -1
        for df_index, df in enumerate(forward_df_list):
            current_time = df.loc[row_index, 'during_time']
            if current_time > max_during_time:
                max_during_time = current_time
                max_df_index = df_index
        select_row = forward_df_list[max_df_index].loc[row_index]
        max_forward_during_time.append({'forward': select_row.get('during_time')})
    return max_forward_during_time


def exporter_db_batch(dp_batch_df):
    all_dp_batch_df = dp_batch_df.copy()

    model_exec_indices = all_dp_batch_df[all_dp_batch_df['name'] == 'modelExec'].index
    batch_indices = all_dp_batch_df[all_dp_batch_df['name'] == 'batchFrameworkProcessing'].index
    logger.debug(f"model_exec_indices_length:{len(model_exec_indices)},content:{model_exec_indices}")
    logger.debug(f"batch_indices_length:{len(batch_indices)},content:{batch_indices}")

    dp_batch_indices = None
    dp_rank_id_indices = None
    dp_batch_df_list = all_dp_batch_df.groupby('pid')
    for pid, dp_batch_df in dp_batch_df_list:
        dp_batch_indices = dp_batch_df[dp_batch_df['name'] == 'dpBatch'].index
        dp_rank_id_indices = dp_batch_df[dp_batch_df['name'] == 'dpRankIds'].index
        if len(dp_batch_indices) != 0 and len(dp_rank_id_indices) != 0:
            logger.debug(f"dp-batch pid:{pid}")
            break
    logger.debug(f"dp_batch_indices_length:{len(dp_batch_indices)},content:{dp_batch_indices}")
    logger.debug(f"dp_rank_id_indices_length:{len(dp_rank_id_indices)},content:{dp_rank_id_indices}")


    try:
        forward_info = get_forward_df(dp_batch_df)
        logger.debug(f"forward_info_length:{len(forward_info)},content:{forward_info}")
    except :
        logger.error('get forward info error')

    for db_batch_index in range(len(dp_batch_indices)):
        dp_batch_row = all_dp_batch_df.loc[dp_batch_indices[db_batch_index]]
        dp_id_list_row = all_dp_batch_df.loc[dp_rank_id_indices[db_batch_index]]

        pre_dp_map = {}
        rid_list = dp_batch_row.get('rid_list')
        dp_id_list = dp_id_list_row.get('rid_list')
        if not is_contained_vaild_dp_batch_info(rid_list, dp_id_list):
            logger.warning('rid_list length is not equal to dp_id_list')
            continue
        for i, value in enumerate(dp_id_list):
            value = str(value)
            dp_name = 'dp' + value
            if dp_name not in pre_dp_map:
                pre_dp_map[dp_name] = []
            pre_dp_map[dp_name].append(rid_list[i])

        for key, value in pre_dp_map.items():
            rid_name = key + '-rid'
            size_name = key + '-size'
            all_dp_batch_df.loc[model_exec_indices[db_batch_index], rid_name] = str(value)
            all_dp_batch_df.loc[model_exec_indices[db_batch_index], size_name] = len(value)
            all_dp_batch_df.loc[batch_indices[db_batch_index], rid_name] = str(value)
            all_dp_batch_df.loc[batch_indices[db_batch_index], size_name] = len(value)

        for key, value in forward_info[db_batch_index].items():
            all_dp_batch_df.loc[model_exec_indices[db_batch_index], key] = str(value)
            all_dp_batch_df.loc[batch_indices[db_batch_index], key] = str(value)

        


    return all_dp_batch_df


class ExporterBatchData(ExporterBase):
    name = "batch_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')
        if df is None:
            logger.warning("The data is empty, please check")
            return
        # mindie 330将BatchScheduler打点修改为batchFrameworkProcessing，此处做新旧版本的兼容处理
        batch_df = df[(df['name'] == 'BatchSchedule') | (df['name'] == 'modelExec') | \
            (df['name'] == 'batchFrameworkProcessing') | (df['name'] == 'dpBatch') | \
            (df['name'] == 'forward') | (df['name'] == 'dpRankIds')]
        if batch_df.empty:
            logger.warning("No batch data found. Please check msproftx.db.")
            return
        try:
            model_df = batch_df[['name', 'res_list', 'start_time', 'end_time', 'batch_size', \
                'batch_type', 'during_time', 'pid', 'rid_list']]
            model_df = exporter_db_batch(model_df)
            model_df = model_df[(model_df['name'] == 'BatchSchedule') | (model_df['name'] == 'modelExec') | \
            (model_df['name'] == 'batchFrameworkProcessing')]
            model_df = model_df.drop(['pid', 'rid_list'], axis=1)
            model_df = model_df.rename(columns={
            'start_time': 'start_time(microsecond)',
            'end_time': 'end_time(microsecond)',
            'during_time': 'during_time(microsecond)'
        })
        except KeyError as e:
            logger.warning(f"Field '{e.args[0]}' not found in msproftx.db.")
        output = cls.args.output_path

        save_dataframe_to_csv(model_df, output, "batch.csv")

        for col in model_df:
            if model_df[col].dtype == 'object':
                model_df[col] = model_df[col].astype(str)
            if col == 'batch_size':
                model_df[col] = model_df[col].astype(float)

        add_table_into_visual_db(model_df, 'batch')
