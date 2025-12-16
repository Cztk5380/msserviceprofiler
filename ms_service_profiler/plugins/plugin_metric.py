# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import pandas as pd

from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import DataFrameMissingError, ColumnMissingError
from ms_service_profiler.utils.timer import timer
from ms_service_profiler.utils.error import KeyExcept


class PluginMetric(PluginBase):
    """Create a new metric table with timestamp and all metric."""

    name = "plugin_metric"
    depends = ["plugin_common", "plugin_req_status"]

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        with KeyExcept('name', 'start_time', 'start_datetime', ignore=True, msg="ignoring current process by default."):
            tx_data_df = data.get('tx_data_df')
            if tx_data_df is None:
                return data

            metric_cols = [col for col in tx_data_df.columns if is_metric(col)]

            missing_col = [col for col in ['name', 'start_time', 'start_datetime'] if col not in tx_data_df.columns]
            if missing_col:
                raise KeyError(*missing_col)

            metric_data_df = tx_data_df[['start_time', 'start_datetime'] + metric_cols].copy()

            if (tx_data_df['name'] == 'decodeReq').any():
                metric_data_df.loc[tx_data_df['name'] == 'decodeReq', 'WAITING+'] = 1.0

            increase_metric_cols = [col for col in metric_cols if col[-1] == "+"]
            metric_data_df[increase_metric_cols] = cal_increase_value(metric_data_df[increase_metric_cols])

            metric_data_df = metric_data_df.rename(columns={col: col[:-1] for col in metric_cols})

            data['metric_data_df'] = metric_data_df
        return data


def is_metric(name):
    if isinstance(name, str) and name and name[-1] in ['+', '=']:
        return True
    return False


def cal_increase_value(df):
    df = df.apply(pd.to_numeric, errors='coerce')
    df = df.fillna(0)
    df = df.cumsum(axis=0)
    return df

