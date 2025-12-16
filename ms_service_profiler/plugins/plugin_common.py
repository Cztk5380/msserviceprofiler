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
        if isinstance(data["tx_data_df"], pd.DataFrame):
            data["tx_data_df"] = data["tx_data_df"].replace(to_replace=np.nan, value=None)
        return data
