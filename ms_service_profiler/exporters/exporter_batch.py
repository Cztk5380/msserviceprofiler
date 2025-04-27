# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from enum import Enum
from pathlib import Path
import json
import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import save_dataframe_to_csv
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.utils import add_table_into_visual_db

# 定义一个函数，用于处理每一行的列表
def extract_dp_values(row):
    return [int(item['dp']) for item in row]

def is_contained_vaild_dp_batch_info(rid_list, dp_id_list):
    if rid_list is None or dp_id_list is None or len(rid_list) != len(dp_id_list):
        return False

    return True


def exporter_db_batch(dp_batch_df):
    all_dp_batch_df = dp_batch_df.copy()
    all_dp_batch_df.loc[all_dp_batch_df['name'] == 'dbBatch', 'dpIds'] = \
        all_dp_batch_df.loc[all_dp_batch_df['name'] == 'dbBatch', 'dpIds'].apply(extract_dp_values)

    model_exec_indices = all_dp_batch_df[all_dp_batch_df['name'] == 'modelExec'].index
    batch_indices = all_dp_batch_df[all_dp_batch_df['name'] == 'batchFrameworkProcessing'].index
    logger.debug(model_exec_indices)
    logger.debug(batch_indices)

    dp_batch_indices = None
    dp_batch_df_list = all_dp_batch_df.groupby('pid')
    for pid, dp_batch_df in dp_batch_df_list:
        dp_batch_indices = dp_batch_df[dp_batch_df['name'] == 'dbBatch'].index
        if len(dp_batch_indices) != 0:
            logger.debug(f"dp-batch pid:{pid}")
            break
    logger.debug(dp_batch_indices)

    # model_index = 0
    # batch_index = 0
    for db_batch_index in range(len(dp_batch_indices)):
        dp_batch_row = all_dp_batch_df.loc[dp_batch_indices[db_batch_index]]

        pre_dp_map = {}
        rid_list = dp_batch_row.get('rid_list')
        dp_id_list = dp_batch_row.get('dpIds')
        if not is_contained_vaild_dp_batch_info(rid_list, dp_id_list):
            logger.warning('rid_list length is not equal to dp_id_list')
            continue
        for i, value in enumerate(dp_id_list):
            value = str(value)
            rid_name = 'dp' + value + '-rid'
            rid_size = 'dp' + value + '-size'
            if rid_name not in pre_dp_map:
                pre_dp_map[rid_name] = []
                pre_dp_map[rid_size] = 0
            pre_dp_map[rid_name].append(str(rid_list[i]))
            pre_dp_map[rid_size] += 1

        # if model_index < len(model_exec_indices) and \
        #     all_dp_batch_df.loc[model_exec_indices[model_index]]['start_time'] > dp_batch_row['end_time']:
        #     for key, value in pre_dp_map.items():
        #         all_dp_batch_df.loc[model_exec_indices[model_index], key] = value
        #     model_index += 1
        # if batch_index < len(batch_indices) and \
        #     all_dp_batch_df.loc[batch_indices[batch_index]] > dp_batch_row['end_time']:
        #     for key, value in pre_dp_map.items():
        #         all_dp_batch_df.loc[batch_indices[batch_index], key] = value
        #     batch_index += 1
        for key, value in pre_dp_map.items():
            all_dp_batch_df.loc[model_exec_indices[db_batch_index], key] = value
            all_dp_batch_df.loc[batch_indices[db_batch_index], key] = value

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
            (df['name'] == 'batchFrameworkProcessing') | (df['name'] == 'dbBatch')]
        if batch_df.empty:
            logger.warning("No batch data found. Please check msproftx.db.")
            return
        try:
            model_df = batch_df[['name', 'res_list', 'start_time', 'end_time', 'batch_size', \
                'batch_type', 'during_time', 'dpIds', 'pid', 'rid_list',]]
            model_df = exporter_db_batch(model_df)
            model_df = model_df[(model_df['name'] == 'BatchSchedule') | (model_df['name'] == 'modelExec') | \
            (model_df['name'] == 'batchFrameworkProcessing')]
            model_df = model_df.drop(['dpIds', 'pid', 'rid_list'], axis=1)
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
