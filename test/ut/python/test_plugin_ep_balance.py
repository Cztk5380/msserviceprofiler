# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
from collections import defaultdict

import pytest
import pandas as pd
from ms_service_profiler.plugins.plugin_ep_balance import PluginEpBalanceProcess


GROUPED_MATMUL_API_NAME = "aclnnGroupedMatmulV4_GroupedMatmul_GroupedMatmul"
GMM_NUM_PER_LAYER = 2
DEEPSEEK_MOE_DECODER_LAYER_NUMS = 58
TOKENS = 20
kernel_start_list = [1000] * (DEEPSEEK_MOE_DECODER_LAYER_NUMS * GMM_NUM_PER_LAYER * TOKENS)
kernel_end_list = [1010] * (DEEPSEEK_MOE_DECODER_LAYER_NUMS * GMM_NUM_PER_LAYER * TOKENS)
kernel_name_list = [GROUPED_MATMUL_API_NAME] * (DEEPSEEK_MOE_DECODER_LAYER_NUMS * GMM_NUM_PER_LAYER * TOKENS)
kernel_id_list = [0] * (DEEPSEEK_MOE_DECODER_LAYER_NUMS * GMM_NUM_PER_LAYER * TOKENS // 2) + \
                 [1] * (DEEPSEEK_MOE_DECODER_LAYER_NUMS * GMM_NUM_PER_LAYER * TOKENS // 2)

kernel_df = pd.DataFrame.from_dict({
    "name": kernel_name_list,
    "start": kernel_start_list,
    "end": kernel_end_list,
    "db_id": kernel_id_list
})


def test_plugin_ep():
    data = {
        "kernel_df": kernel_df
    }
    golden_result = [200] * DEEPSEEK_MOE_DECODER_LAYER_NUMS
    result = PluginEpBalanceProcess.parse(data)
    assert golden_result == result["ep_balance"][0].tolist()
    assert golden_result == result["ep_balance"][1].tolist()
