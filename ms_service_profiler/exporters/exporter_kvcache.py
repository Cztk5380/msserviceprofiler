# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from enum import Enum   

from pathlib import Path
import json
import pandas as pd
from matplotlib import pyplot as plt

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.parse import save_dataframe_to_csv


class ExporterKVCacheData(ExporterBase):
    name = "kvcache_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')

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