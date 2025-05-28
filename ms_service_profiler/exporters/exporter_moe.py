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


OUTPUT_CSV_NAME = "moe_analysis.csv"
NAME = "moe_analysis"


class ExporterMoe(ExporterBase):
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

        moe_analysis_df = data[NAME]

        save_dataframe_to_csv(moe_analysis_df, output, OUTPUT_CSV_NAME)

        moe_analysis_arr = moe_analysis_df.values

        output_path = os.path.join(output, "grouped_matmul_heat_map.png")
        plot_confidence_interval(moe_analysis_arr, output_path)


def plot_confidence_interval(ci_df, output_path):
    plt.figure(figsize=(10, 6))

    # 绘制置信区间
    plt.errorbar(ci_df['Dataset'], ci_df['Mean'],
                 yerr=[ci_df['Mean'] - ci_df['CI_Lower'], ci_df['CI_Upper'] - ci_df['Mean']],
                 fmt='o', color='blue', ecolor='gray', elinewidth=2, capsize=5)

    plt.title("95% Confidence Intervals for Each Dataset")
    plt.xlabel("Dataset Number")
    plt.ylabel("Mean Value")
    plt.grid(True)
    # plt.show()
    plt.savefig(output_path)