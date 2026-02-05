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

from collections import namedtuple


# Revised ProfilerMock that properly tracks instance calls
class Profiler:
    instance_calls = []

    def __init__(self, level=None):
        self.calls = []
        Profiler.instance_calls.append(self.calls)

    @classmethod
    def reset(cls):
        cls.instance_calls = []

    def domain(self, name):
        self.calls.append(("domain", name))
        return self

    def res(self, res_id):
        self.calls.append(("res", res_id))
        return self

    def event(self, event_name):
        self.calls.append(("event", event_name))
        return self

    def metric(self, name, value):
        self.calls.append(("metric", name, value))
        return self

    def metric_scope(self, name, value):
        self.calls.append(("metric_scope", name, value))
        return self

    def metric_inc(self, name, value):
        self.calls.append(("metric_inc", name, value))
        return self

    def span_start(self, name):
        self.calls.append(("span_start", name))
        return self

    def span_end(self):
        self.calls.append("span_end")
        return self

    def attr(self, name, value):
        self.calls.append(("attr", name, value))
        return self


# Create fake modules in sys.modules
Level = namedtuple("Level", ["INFO"])("INFO")