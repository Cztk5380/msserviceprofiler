# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
import os
from abc import abstractmethod
from typing import Dict

import matplotlib.pyplot as plt

from ms_service_profiler.exporters.base import ExporterBase
from ms_service_profiler.exporters.utils import save_dataframe_to_csv, add_table_into_visual_db
from ms_service_profiler.utils.file_open_check import UmaskWrapper


OUTPUT_CSV_NAME = "ep_balance.csv"
OUTPUT_PNG_NAME = "ep_balance.png"
NAME = "ep_balance"
MAX_PLT_PIXEL = 2560
MIN_PLT_PIXEL = 32


class ExporterEpBalance(ExporterBase):
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

        output = cls.args.output_path

        if NAME not in data.keys() or data[NAME].empty:
            return

        ep_balance_df = data[NAME]

        if "csv" in cls.args.format:
            save_dataframe_to_csv(ep_balance_df, output, OUTPUT_CSV_NAME)

        if "db" in cls.args.format:
            add_table_into_visual_db(ep_balance_df, NAME)

        heat_map = ep_balance_df.values

        x_pixel = max(min(len(ep_balance_df.cloumns) // 10, MAX_PLT_PIXEL), MIN_PLT_PIXEL)
        y_pixel = max(min(len(ep_balance_df) // 10, MAX_PLT_PIXEL), MIN_PLT_PIXEL)

        plt.figure(figsize=(x_pixel, y_pixel))
        plt.imshow(heat_map)
        plt.tight_layout()
        plt.title("GMM duration of different devices and decoder_layers")
        plt.xlabel("processId from different devices")
        plt.xticks(labels=list(ep_balance_df.columns))
        plt.ylabel("decoder_layers")
        plt.yticks(labels=[i for i in range(len(ep_balance_df))])
        plt_output_path = os.path.join(output, OUTPUT_PNG_NAME)
        with UmaskWrapper(umask=0o137):
            plt.savefig(plt_output_path)
