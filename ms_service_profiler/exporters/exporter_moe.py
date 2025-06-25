# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import os
from abc import abstractmethod
from typing import Dict

import matplotlib.pyplot as plt

from ms_service_profiler.exporters.base import TaskExporterBase
from ms_service_profiler.exporters.utils import save_dataframe_to_csv, add_table_into_visual_db
from ms_service_profiler.utils.file_open_check import UmaskWrapper


OUTPUT_CSV_NAME = "moe_analysis.csv"
OUTPUT_PNG_NAME = "moe_analysis.png"
NAME = "moe_analysis"


class ExporterMoe(TaskExporterBase):
    name: str = NAME

    @classmethod
    @abstractmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    @abstractmethod
    def export(cls, data: Dict) -> None:
        if not data:
            return
        if NAME not in data.keys() or data[NAME].empty:
            return

        output = cls.args.output_path

        moe_analysis_df = data[NAME]

        if 'csv' in cls.args.format:
            save_dataframe_to_csv(moe_analysis_df, output, OUTPUT_CSV_NAME)

        if "db" in cls.args.format:
            add_table_into_visual_db(moe_analysis_df, NAME)

        plt_output_path = os.path.join(output, OUTPUT_PNG_NAME)
        plot_confidence_interval(moe_analysis_df, plt_output_path)

    @classmethod
    def depends(cls):
        return ["pipeline:mspti"]
 
    def do_export(self) -> None:
        data: Dict = self.get_depends_result("pipeline:mspti")
        self.export(data)


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

    with UmaskWrapper(umask=0o137):
        plt.savefig(output_path)
