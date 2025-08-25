# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

__all__ = ['PluginMsptiProcess', 'PluginEpBalanceProcess', 'PluginMoeSlowRankProcess']


from ms_service_profiler.plugins.plugin_common import PluginCommon
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStamp
from ms_service_profiler.plugins.plugin_metric import PluginMetric
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus
from ms_service_profiler.plugins.plugin_concat import PluginConcat
from ms_service_profiler.plugins.plugin_trace import PluginTrace
from ms_service_profiler.plugins.plugin_process_name import PluginProcessName
from ms_service_profiler.plugins.plugin_batch import PluginBatch
from ms_service_profiler.plugins.plugin_mspit_process import PluginMsptiProcess
from ms_service_profiler.plugins.plugin_ep_balance import PluginEpBalanceProcess
from ms_service_profiler.plugins.plugin_moe import PluginMoeSlowRankProcess
from ms_service_profiler.plugins.plugin_dynamic_ep_balance import PluginDyEpBalance

builtin_plugins = [PluginTimeStamp, PluginConcat, PluginCommon, PluginMetric, PluginTrace,
    PluginProcessName, PluginBatch, PluginDyEpBalance]

custom_plugins = [PluginReqStatus]

