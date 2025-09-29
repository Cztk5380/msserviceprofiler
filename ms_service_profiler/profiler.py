# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import json
from enum import Enum
from ms_service_profiler.mstx import service_profiler


class MarkType(int, Enum):
    TYPE_EVENT = 0
    TYPE_METRIC = 1
    TYPE_SPAN = 2
    TYPE_LINK = 3


class Level(int, Enum):
    ERROR = 10                  # 20260630 日落
    INFO = 20                   # 20260630 日落
    DETAILED = 30               # 20260630 日落
    VERBOSE = 40                # 20260630 日落
    LEVEL_CORE_TRACE = 10       # 最核心的数据，请求关键事件，比如请求到达，请求返回，batch 大小，forward 时长
    LEVEL_OUTLIER_ENENT = 10    # 异常、关键事件。比如发生了Swap，或者发生了重计算
    LEVEL_NORMAL_TRACE = 20     # 普通 Trace 数据
    LEVEL_DETAILED_TRACE = 30   # 包含更多，更大量的详细信息
    L0 = 10
    L1 = 20
    L2 = 30


class Profiler:
    def __init__(self, profiler_level) -> None:
        self._enable = service_profiler.is_enable(profiler_level)
        self._attr = dict()
        self._span_handle = None

    @property
    def enable(self):
        return self._enable

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.span_end()

    def attr(self, key, value):
        self._attr[key] = value
        return self

    def domain(self, domain):
        self._enable = self._enable and service_profiler.is_domain_enable(domain)
        return self.attr("domain", domain)

    def res(self, res):
        return self.attr("rid", res)

    def metric(self, metric_name, metric_value):
        return self.attr(f"{metric_name}=", metric_value)

    def metric_inc(self, metric_name, metric_value):
        return self.attr(f"{metric_name}+", metric_value)

    def metric_scope(self, scope_name, scope_value=0):
        return self.attr(f"scope#{scope_name}", scope_value)

    def metric_scope_as_req_id(self):
        return self.attr("scope#", "req")

    def launch(self):
        if self._enable:
            service_profiler.mark_event(self.get_msg())

    def get_msg(self):
        return json.dumps(self._attr)

    def link(self, from_rid, to_rid):
        if self._enable:
            self.attr("type", MarkType.TYPE_LINK).attr("from", from_rid).attr("to", to_rid)
            service_profiler.mark_event(self.get_msg())

    def event(self, event_name):
        if self._enable:
            self.attr("type", MarkType.TYPE_EVENT).attr("name", event_name)
            service_profiler.mark_event(self.get_msg())

    def span_start(self, span_name):
        if self._enable:
            self.attr("name", span_name).attr("type", MarkType.TYPE_SPAN)
            self._span_handle = service_profiler.start_span(span_name)
        return self

    def span_end(self):
        if self._enable:
            service_profiler.mark_span_attr(self.get_msg(), self._span_handle)
            service_profiler.end_span(self._span_handle)

    def add_meta_info(self, meta_key, meta_data):
        if self._enable:
            service_profiler.add_meta_info(meta_key, str(meta_data))
