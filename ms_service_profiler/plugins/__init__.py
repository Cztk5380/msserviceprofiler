# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

from ms_service_profiler.plugins.plugin_common import PluginCommon
from ms_service_profiler.plugins.plugin_timestamp import PluginTimeStamp
from ms_service_profiler.plugins.plugin_metric import PluginMetric
from ms_service_profiler.plugins.plugin_req_status import PluginReqStatus

buildin_plugins = [PluginCommon, PluginTimeStamp, PluginMetric]

custom_plugins = [PluginReqStatus]

