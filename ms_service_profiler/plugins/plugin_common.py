# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import pandas as pd
import numpy as np
from ms_service_profiler.plugins.base import PluginBase
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import DataFrameMissingError
from ms_service_profiler.utils.timer import timer


class PluginCommon(PluginBase):
    name = "plugin_common"
    depends = ["plugin_concat"]

    @classmethod
    @timer(logger.debug)
    def parse(cls, data):
        if data.get("tx_data_df") is None:
            return data

        data["tx_data_df"] = data["tx_data_df"].replace(to_replace=np.nan, value=None)
        return data