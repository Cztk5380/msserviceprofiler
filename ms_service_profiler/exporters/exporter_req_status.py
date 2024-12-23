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

import pandas as pd

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.plugins.plugin_req_status import ReqStatus
from ms_service_profiler.exporters.utils import add_table_into_visual_db


class ExporterReqStatus(ExporterBase):
    name = "req_status"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        metrics = data.get('metric_data_df')
        req_status_cols = [col for col in metrics.columns if col in ReqStatus.__members__]

        df = metrics[req_status_cols]
        df.insert(0, 'time/us', metrics['start_time'] - metrics['start_time'].iloc[0])
        df = df.astype(int)

        add_table_into_visual_db(df, 'request_status')
