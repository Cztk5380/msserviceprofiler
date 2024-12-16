# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from enum import Enum
from ms_service_profiler.mstx import service_profiler


class MarkType(int, Enum):
    TYPE_EVENT = 0
    TYPE_METRIC = 1
    TYPE_SPAN = 2
    TYPE_LINK = 3


class Level(int, Enum):
    ERROR = 10
    INFO = 20
    DETAILED = 30
    VERBOSE = 40


class Profiler:
    def __init__(self, profiler_level) -> None:
        self._enable = service_profiler.is_enable(profiler_level)
        self._attr = dict()
        self._span_handle = None

    def attr(self, key, value):
        self._attr[key] = value
        return self

    def domain(self, domain):
        self.attr("domain", domain)
        return self

    def res(self, res):
        self.attr("rid", res)
        return self

    def metric(self, metric_name, metric_value):
        self.attr(f"{metric_name}=", metric_value)
        return self

    def metric_inc(self, metric_name, metric_value):
        self.attr(f"{metric_name}+", metric_value)
        return self

    def metric_scope(self, scope_name, scope_value=0):
        self.attr(f"scope#{scope_name}", scope_value)
        return self

    def metric_scope_as_req_id(self):
        self.attr(f"scope#", "req")
        return self

    def launch(self):
        if self._enable:
            service_profiler.mark_event(self.get_msg())

    def get_msg(self):
        return json.dumps(self._attr)

    def link(self, from_rid, to_rid):
        if self._enable:
            self.attr("type", MarkType.TYPE_LINK)
            self.attr("from", from_rid)
            self.attr("to", to_rid)
            service_profiler.mark_event(self.get_msg())

    def event(self, event_name):
        if self._enable:
            self.attr("type", MarkType.TYPE_EVENT)
            self.attr("name", event_name)
            service_profiler.mark_event(self.get_msg())

    def span_start(self, span_name):
        if self._enable:
            self.attr("name", span_name)
            self.attr("type", MarkType.TYPE_SPAN)
            self._span_handle = service_profiler.start_span()
        return self

    def span_end(self):
        if self._enable:
            service_profiler.mark_span_attr(self.get_msg(), self._span_handle)
            service_profiler.end_span(self._span_handle)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.span_end()
