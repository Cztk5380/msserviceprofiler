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


class AttrCollect:
    def __init__(self) -> None:
        self._attr = dict()

    def add_attr(self, key, value):
        self._attr[key] = value

    def get_msg(self):
        return json.dumps(self._attr)


class Span(AttrCollect):
    def __init__(self, span_name, rid, profiler_level) -> None:
        super().__init__()
        self._enable = service_profiler.is_enable(profiler_level)

        if not self._enable:
            return

        self._span_handle = 0
        if rid is not None:
            self.add_attr("rid", rid)

        self.add_attr("type", MarkType.TYPE_SPAN)
        self.add_attr("name", span_name)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()

    def start(self):
        if self._enable:
            self._span_handle = service_profiler.start_span()

    def end(self):
        if self._enable:
            service_profiler.mark_span_attr(self.get_msg(), self._span_handle)
            service_profiler.end_span(self._span_handle)


class Metric(AttrCollect):
    def __init__(self, profiler_level) -> None:
        super().__init__()
        self._enable = service_profiler.is_enable(profiler_level)
        if not self._enable:
            return

    @staticmethod
    def add_metric(metric_name, value, rid, profiler_level):
        Metric(profiler_level).mark(metric_name, value)

    def mark(self, metric_name, value, rid):
        if self._enable:
            self.add_attr("type", MarkType.TYPE_METRIC)
            self.add_attr("name", metric_name)
            self.add_attr("value", value)
            if rid is not None:
                self.add_attr("rid", rid)
            service_profiler.mark_event(self.get_msg())


class Event(AttrCollect):
    def __init__(self, profiler_level) -> None:
        super().__init__()
        if not self._enable:
            return

    @staticmethod
    def add_event(event_name, value, rid, profiler_level):
        Event(profiler_level).mark(event_name, value, rid)

    def mark(self, event_name, value, rid):
        if self._enable:
            self.add_attr("type", MarkType.TYPE_EVENT)
            self.add_attr("name", event_name)
            self.add_attr("value", value)
            if rid is not None:
                self.add_attr("rid", rid)
            service_profiler.mark_event(self.get_msg())


class ResLink(AttrCollect):
    def __init__(self, profiler_level) -> None:
        super().__init__()
        self._enable = service_profiler.is_enable(profiler_level)
        if not self._enable:
            return

    @staticmethod
    def link(from_rid, to_rid, profiler_level):
        ResLink(profiler_level).mark(from_rid, to_rid)

    def mark(self, from_rid, to_rid):
        if self._enable:
            self.add_attr("type", MarkType.TYPE_LINK)
            self.add_attr("from", from_rid)
            self.add_attr("to", to_rid)
            service_profiler.mark_event(self.get_msg())
