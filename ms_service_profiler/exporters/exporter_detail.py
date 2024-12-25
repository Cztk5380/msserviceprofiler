# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from pathlib import Path

import pandas as pd
from ms_service_profiler.exporters.base import ExporterBase


class ExporterDetail(ExporterBase):
    name = "detail"

    @classmethod
    def initialize(cls, args):
        cls.args = args

    @classmethod
    def export(cls, data) -> None:
        for k, v in data.items():
            filename = Path(cls.args.output_path) / f'{k}.txt'
            if isinstance(v, pd.DataFrame):
                v.to_csv(filename.with_suffix('.csv'), index=False)
            else:
                filename.write_text(f"{k}: {v}")