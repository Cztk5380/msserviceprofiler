# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from enum import Enum   
import logging
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
        batch_df = df[(df['name'] == 'BatchSchedule') | (df['name'] == 'modelExec')]
        if batch_df.empty:
            logging.warning("No batch data found. Please check msproftx.db.")
            return
        model_df = batch_df[['name', 'res_list', 'start_time', 'end_time', 'batch_size', 'batch_type', 'during_time',]]
        model_df = model_df.rename(columns={
            'start_time': 'start_time(microsecond)',
            'end_time': 'end_time(microsecond)',
            'during_time': 'during_time(microsecond)'
        })

        output = cls.args.output_path

        save_dataframe_to_csv(model_df, output, "batch.csv")
