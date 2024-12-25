# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from enum import Enum   

from pathlib import Path
import json
import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.parse import save_dataframe_to_csv
from ms_service_profiler.utils.log import logger


class ExporterBatchData(ExporterBase):
    name = "batch_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')
        if df is None:
            logger.error("The data is empty, please check")
            return
        batch_df = df[df['name'] == 'BatchSchedule']
        modelexec_df = df[df['name'] == 'modelExec']
        batch_df_copy = batch_df.copy()
        modelexec_df_copy = modelexec_df.copy()
        # 在副本上进行操作
        batch_df_copy.loc[:, 'resList'] = batch_df_copy['message'].apply(lambda x: x['rid'])
        modelexec_df_copy.loc[:, 'resList'] = modelexec_df_copy['message'].apply(lambda x: x['rid'])
        result_df = pd.concat([batch_df_copy, modelexec_df_copy], ignore_index=True)
        result_df = result_df.sort_values(by='start_time')
        model_df = result_df[['name', 'resList', 'start_time', 'end_time', 'batch_size', 'batch_type', 'during_time',]]
        model_df = model_df.rename(columns={
            'resList': 'res_list',
            'start_time': 'start_time(microsecond)',
            'end_time': 'end_time(microsecond)',
            'during_time': 'during_time(microsecond)'
        })

        output = cls.args.output_path
        save_dataframe_to_csv(model_df, output, "batch.csv")

