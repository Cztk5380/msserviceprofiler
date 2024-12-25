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
from collections import defaultdict

import pandas as pd

from ms_service_profiler.plugins.base import PluginBase


class PluginConcat(PluginBase):
    name = "plugin_concat"
    depends = ["plugin_timestamp"]

    @classmethod
    def parse(cls, data_list):
        merged_data = defaultdict(pd.DataFrame)
        for data in data_list:
            for key, value in data.items():
                if isinstance(value, pd.DataFrame):
                    merged_data[key] = pd.concat([merged_data[key], value], ignore_index=True)
                print(key, len((merged_data[key])))
        for key, value in merged_data.items():
            merged_data[key] = merged_data[key].sort_values(by='start_time', ascending=True).reset_index(drop=True)
            merged_data[key].to_csv(key + ".csv")
        return merged_data
