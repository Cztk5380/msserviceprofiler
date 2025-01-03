# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

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

        df = metrics[req_status_cols].astype(int)
        df.insert(0, 'timestamp', metrics['start_datetime'])

        add_table_into_visual_db(df, 'request_status')
