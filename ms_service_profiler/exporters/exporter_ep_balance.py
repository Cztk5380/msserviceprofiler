# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from abc import abstractmethod
from typing import Dict
import os

from ms_service_profiler.utils.trace_to_db import TRACE_TABLE_DEFINITIONS
from ms_service_profiler.utils.log import logger
from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import save_dataframe_to_csv
from ms_service_profiler.exporters.exporter_trace import save_trace_data_into_json, save_trace_data_into_db
from ms_service_profiler.exporters.utils import create_sqlite_tables
import matplotlib.pyplot as plt


OUTPUT_CSV_NAME = "ep_balance.csv"
NAME = "ep_balance"


class ExporterEpBalance(ExporterBase):
    name: str = NAME

    @classmethod
    @abstractmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @abstractmethod
    def export(cls, data: Dict) -> None:
        if 'db' not in cls.args.format and 'json' not in cls.args.format:
            return

        if not data:
            return

        output = cls.args.output_path

        if NAME not in data.keys() or data[NAME].empty:
            return

        ep_balance_df = data[NAME]

        # save_dataframe_to_csv(ep_balance_df, output, OUTPUT_CSV_NAME)

        heat_map = ep_balance_df.values

        plt.figure(figsize=(50, 50))
        plt.imshow(heat_map)
        plt.tight_layout()
        output_path = os.path.join(output, "grouped_matmul_heat_map.png")
        plt.savefig(output_path)
