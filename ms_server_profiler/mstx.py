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

import ctypes
import logging


class LibserverProfiler:
    lib_server_profiler = None

    def __init__(self) -> None:
        try:
            self.lib = ctypes.cdll.LoadLibrary("libms_server_profiler.so")
        except Exception as ex:
            logging.error("libserver_profiler.so load failed.%s", ex)
            self.lib = None

        self.func_start_span = None
        self.func_end_span = None
        self.func_mark_span_attr = None
        self.func_mark_event = None
        self.func_start_server_profiler = None
        self.func_stop_server_profiler = None
        self.func_is_enable = None

        if self.lib is not None:
            self.func_start_span = self.lib.StartSpan
            self.func_start_span.restype = ctypes.c_ulonglong
            self.func_end_span = self.lib.EndSpan
            self.func_end_span.argtypes = (ctypes.c_ulonglong,)
            self.func_mark_span_attr = self.lib.MarkSpanAttr
            self.func_mark_span_attr.argtypes = (ctypes.c_char_p, ctypes.c_ulonglong)
            self.func_mark_event = self.lib.MarkEvent
            self.func_mark_event.argtypes = (ctypes.c_char_p,)
            self.func_start_server_profiler = self.lib.StartServerProfiler
            self.func_stop_server_profiler = self.lib.StopServerProfiler
            self.func_is_enable = self.lib.IsEnable
            self.func_is_enable.argtypes = (ctypes.c_ulong,)
            self.func_is_enable.restype = ctypes.c_bool

    def start_span(self):
        if self.func_start_span is None:
            return 0
        return self.func_start_span()

    def end_span(self, span_handle):
        if self.func_end_span is not None:
            self.func_end_span(span_handle)

    def mark_span_attr(self, msg, span_handle):
        if self.func_mark_span_attr is not None:
            self.func_mark_span_attr(bytes(msg, encoding="utf-8"), span_handle)

    def mark_event(self, msg):
        if self.func_mark_event is not None:
            self.func_mark_event(bytes(msg, encoding="utf-8"))

    def start_profiler(self):
        if self.func_start_server_profiler is not None:
            self.func_start_server_profiler()

    def stop_profiler(self):
        if self.func_stop_server_profiler is not None:
            self.func_stop_server_profiler()

    def is_enable(self, profiler_level):
        if self.func_is_enable is None:
            return False
        return self.func_is_enable(profiler_level)


server_profiler = LibserverProfiler()
