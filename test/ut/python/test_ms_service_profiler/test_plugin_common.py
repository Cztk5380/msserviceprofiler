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
import pytest
import pandas as pd
import numpy as np
from ms_service_profiler.plugins import PluginCommon
from ms_service_profiler.utils.log import logger
from ms_service_profiler.utils.error import ParseError, DataFrameMissingError, KeyMissingError, ValidationError


def test_parse_with_invalid_rid():
    tx_data_df = pd.DataFrame({
        "rid": [np.nan, np.nan, np.nan],
        "type": [3, 3, 3]
    })
    result = PluginCommon.parse({"tx_data_df": tx_data_df})
    assert "tx_data_df" in result
    assert result["tx_data_df"].iloc[2]["rid"] == None

def test_parse_with_missing_df():
    assert {} == PluginCommon.parse({})