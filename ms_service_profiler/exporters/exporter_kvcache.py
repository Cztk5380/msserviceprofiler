# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from enum import Enum   

from pathlib import Path
import json
import logging
import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.parse import save_dataframe_to_csv
from ms_service_profiler.utils.log import logger


class ExporterKVCacheData(ExporterBase):
    name = "kvcache_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')
        if df is None:
            logger.error("The data is empty, please check")
            return
        kvcache_df = df[df['domain'] == 'KVCache']
        kvcache_df = kvcache_df.rename(columns={'deviceKvCache=': 'deviceKvCache'})
        kvcache_df = kvcache_df[['domain', 'rid', 'start_time', 'end_time', 'action', \
            'deviceKvCache', 'during_time']]
        kvcache_df = kvcache_df.rename(columns={
            'deviceKvCache': 'device_kvcache_left',
            'start_time': 'start_time(microsecond)',
            'end_time': 'end_time(microsecond)',
            'during_time': 'during_time(microsecond)'
        })
        output = cls.args.output_path
        save_dataframe_to_csv(kvcache_df, output, "kvcache.csv")