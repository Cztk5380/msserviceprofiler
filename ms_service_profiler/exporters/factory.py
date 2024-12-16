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

from ms_service_profiler.exporters.exporter_trace import ExporterTrace
from ms_service_profiler.exporters.exporter_detail import ExporterDetail
from ms_service_profiler.exporters.exporter_req_status import ExporterReqStatus


# 插件工厂类
class ExporterFactory:
    exporter_cls = [ExporterTrace, ExporterReqStatus, ExporterDetail]

    @staticmethod
    def create_exporters(args):
        exporters = []
        for name in args.exporter:
            exporters.append(ExporterFactory.create(name, args))
        return exporters
    
    @staticmethod
    def create(name, args):
        for exporter in ExporterFactory.exporter_cls:
            if exporter.name == name:
                exporter.initialize(args)
                return exporter
        raise ValueError(f"未知的Exporter名称: {name}")
