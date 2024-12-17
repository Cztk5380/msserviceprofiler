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
from ms_service_profiler.parse import df_to_sqlite


class ExporterKVCacheData(ExporterBase):
    name = "kvcache_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')

        kvcache_df = df[df['domain'] == 'KVCache']
        kvcache_df = kvcache_df.rename(columns={'=deviceKvCache': 'deviceKvCache'})
        kvcache_df = kvcache_df[['message', 'domain', 'start_time', 'end_time', 'action', 'deviceKvCache', 'during_time']]
        kvcache_df['message'] = kvcache_df['message'].astype(str)
        output = cls.args.output_path
        if output is not None:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_name = 'kvcache_output.csv'
            file_path = output_path / file_name
            kvcache_df.to_csv(file_path, index=False)
        if cls.args.sqlite:
            sqlite_file = output_path / "data.db"
            df_to_sqlite(kvcache_df, sqlite_file, 'kvcache')