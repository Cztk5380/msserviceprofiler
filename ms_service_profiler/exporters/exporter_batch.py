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


class ExporterBatchData(ExporterBase):
    name = "batch_data"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        df = data.get('tx_data_df')


        batch_df = df[df['name'] == 'BatchSchedule']
        modelexec_df = df[df['name'] == 'modelExec']
        batch_df['resList'] = batch_df['message'].apply(lambda x: x['rid'])
        modelexec_df['resList'] = modelexec_df['message'].apply(lambda x: x['rid'])
        
        result_df = pd.concat([batch_df, modelexec_df], ignore_index=True)
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

