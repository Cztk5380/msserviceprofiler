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

__all__ = ['PluginMsptiProcess', 'PluginEpBalanceProcess', 'PluginMoeSlowRankProcess']


from ms_service_profiler.plugins.plugin_common import PluginCommon
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStamp
from ms_service_profiler.plugins.plugin_metric import PluginMetric
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus
from ms_service_profiler.plugins.plugin_concat import PluginConcat
from ms_service_profiler.plugins.plugin_trace import PluginTrace
from ms_service_profiler.plugins.plugin_process_name import PluginProcessName
from ms_service_profiler.plugins.plugin_mspit_process import PluginMsptiProcess
from ms_service_profiler.plugins.plugin_ep_balance import PluginEpBalanceProcess
from ms_service_profiler.plugins.plugin_moe import PluginMoeSlowRankProcess

builtin_plugins = [PluginTimeStamp, PluginConcat, PluginCommon, PluginMetric, PluginTrace,
    PluginProcessName]

custom_plugins = [PluginReqStatus]

