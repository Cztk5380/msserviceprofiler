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