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

import ctypes
from ms_service_profiler.utils.file_open_check import get_valid_lib_path


class LibServiceProfiler:
    lib_service_profiler = None

    def __init__(self) -> None:
        self.is_initialized = False
        self.func_start_span = None
        self.func_end_span = None
        self.func_mark_span_attr = None
        self.func_mark_event = None
        self.func_mark_event_ex = None
        self.func_start_service_profiler = None
        self.func_stop_service_profiler = None
        self.func_is_enable = None
        self.func_add_meta_info = None
        self.func_is_valid_dommain = None
        self.lib = None

        self.func_start_span_with_name = None
        self.func_end_span = None
        self.func_span_end_ex = None
        self.func_mark_span_attr = None
        self.func_mark_event = None
        self.func_start_service_profiler = None
        self.func_stop_service_profiler = None
        self.func_is_enable = None
        self.func_is_valid_dommain = None
        self.func_add_meta_info = None

        self.func_get_prof_path = None
        self.func_get_acl_task_time_level = None
        self.func_get_acl_prof_aicore_metrics = None
        self.func_get_torch_prof_step_num = None
        self.func_get_torch_prof_stack = None
        self.func_get_torch_prof_modules = None
        self.func_get_torch_profiler_enable = None

    def init(self) -> None:
        if self.is_initialized:
            return

        self.is_initialized = True
        so_name = "libms_service_profiler.so"
        fp = get_valid_lib_path(so_name)

        if not fp:
            self.lib = None
            return

        try:
            self.lib = ctypes.cdll.LoadLibrary(fp)
        except Exception:
            self.lib = None

        if self.lib is not None:
            self.func_start_span_with_name = self.lib.StartSpanWithName
            self.func_start_span_with_name.argtypes = (ctypes.c_char_p,)
            self.func_start_span_with_name.restype = ctypes.c_ulonglong

            self.func_end_span = self.lib.EndSpan
            self.func_end_span.argtypes = (ctypes.c_ulonglong,)
            self.func_mark_span_attr = self.lib.MarkSpanAttr
            self.func_mark_span_attr.argtypes = (ctypes.c_char_p, ctypes.c_ulonglong)
            self.func_mark_event = self.lib.MarkEvent
            self.func_mark_event.argtypes = (ctypes.c_char_p,)
            try:
                self.func_mark_event_ex = self.lib.MarkEventEx
                self.func_mark_event_ex.argtypes = (
                    ctypes.c_char_p,  # name
                    ctypes.c_char_p,  # domain
                    ctypes.c_char_p  # msg
                )
            except AttributeError:
                self.func_mark_event_ex = None
            try:
                self.func_span_end_ex = self.lib.SpanEndEx
                self.func_span_end_ex.argtypes = (
                    ctypes.c_char_p,  # name
                    ctypes.c_char_p,  # domain
                    ctypes.c_char_p,  # msg
                    ctypes.c_ulonglong  # spanHandle
                )
            except AttributeError:
                self.func_span_end_ex = None
            self.func_start_service_profiler = self.lib.StartServerProfiler
            self.func_stop_service_profiler = self.lib.StopServerProfiler
            self.func_is_enable = self.lib.IsEnable
            self.func_is_enable.argtypes = (ctypes.c_ulong,)
            self.func_is_enable.restype = ctypes.c_bool
            self._init()

    def _init(self):
        if hasattr(self.lib, "IsValidDomain"):
            self.func_is_valid_dommain = self.lib.IsValidDomain
            self.func_is_valid_dommain.argtypes = (ctypes.c_char_p,)
            self.func_is_valid_dommain.restype = ctypes.c_bool

        if hasattr(self.lib, "AddMetaInfo"):
            self.func_add_meta_info = self.lib.AddMetaInfo
            self.func_add_meta_info.argtypes = (ctypes.c_char_p, ctypes.c_char_p)

        if hasattr(self.lib, "GetProfPath"):
            self.func_get_prof_path = self.lib.GetProfPath
            self.func_get_prof_path.restype = ctypes.c_char_p

        if hasattr(self.lib, "GetAclTaskTimeLevel"):
            self.func_get_acl_task_time_level = self.lib.GetAclTaskTimeLevel
            self.func_get_acl_task_time_level.restype = ctypes.c_char_p

        if hasattr(self.lib, "GetAclProfAicoreMetrics"):
            self.func_get_acl_prof_aicore_metrics = self.lib.GetAclProfAicoreMetrics
            self.func_get_acl_prof_aicore_metrics.restype = ctypes.c_int

        if hasattr(self.lib, "GetTorchProfStepNum"):
            self.func_get_torch_prof_step_num = self.lib.GetTorchProfStepNum
            self.func_get_torch_prof_step_num.restype = ctypes.c_int

        if hasattr(self.lib, "GetTorchProfStack"):
            self.func_get_torch_prof_stack = self.lib.GetTorchProfStack
            self.func_get_torch_prof_stack.restype = ctypes.c_bool

        if hasattr(self.lib, "GetTorchProfModules"):
            self.func_get_torch_prof_modules = self.lib.GetTorchProfModules
            self.func_get_torch_prof_modules.restype = ctypes.c_bool

        if hasattr(self.lib, "GetTorchProfilerEnable"):
            self.func_get_torch_profiler_enable = self.lib.GetTorchProfilerEnable
            self.func_get_torch_profiler_enable.restype = ctypes.c_bool

        if hasattr(self.lib, "MarkEventEx"):
            self.func_mark_event_ex = self.lib.MarkEventEx
            self.func_mark_event_ex.argtypes = (ctypes.c_char_p,)

    def start_span(self, name=None):
        self.init()
        if self.func_start_span_with_name is None:
            return 0
        msg = "" if name is None else name
        return self.func_start_span_with_name(bytes(msg, encoding="utf-8"))

    def end_span(self, span_handle):
        self.init()
        if self.func_end_span is not None:
            self.func_end_span(span_handle)

    def mark_span_attr(self, msg, span_handle):
        self.init()
        if self.func_mark_span_attr is not None:
            self.func_mark_span_attr(bytes(msg, encoding="utf-8"), span_handle)

    def mark_event(self, msg):
        self.init()
        if self.func_mark_event is not None:
            self.func_mark_event(bytes(msg, encoding="utf-8"))

    def mark_event_ex(self, name: str, domain: str, msg: str):
        self.init()
        if self.func_mark_event_ex is not None:
            self.func_mark_event_ex(
                bytes(name, "utf-8"),
                bytes(domain, "utf-8"),
                bytes(msg, "utf-8")
            )
        elif self.func_mark_event is not None:
            import json
            legacy = json.dumps({"name": name, "domain": domain, "msg": msg}, ensure_ascii=False)
            self.func_mark_event(bytes(legacy, "utf-8"))

    def span_end_ex(self, name: str, domain: str, msg: str, span_handle: int):
        self.init()
        if self.func_span_end_ex is not None:
            self.func_span_end_ex(
                bytes(name, "utf-8"),
                bytes(domain, "utf-8"),
                bytes(msg, "utf-8"),
                span_handle
            )
        elif self.func_end_span is not None:
            self.func_end_span(span_handle)
            if self.func_mark_event is not None:
                import json
                extra = json.dumps({
                    "type": "span_end_fallback",
                    "name": name,
                    "domain": domain,
                    "msg": msg
                }, ensure_ascii=False)
                self.func_mark_event(bytes(extra, "utf-8"))

    def start_profiler(self):
        self.init()
        if self.func_start_service_profiler is not None:
            self.func_start_service_profiler()

    def stop_profiler(self):
        self.init()
        if self.func_stop_service_profiler is not None:
            self.func_stop_service_profiler()

    def is_enable(self, profiler_level):
        self.init()
        if self.func_is_enable is None:
            return False
        return self.func_is_enable(profiler_level)

    def is_domain_enable(self, domain_name):
        self.init()
        if self.func_is_valid_dommain is None:
            return True
        return self.func_is_valid_dommain(bytes(domain_name, encoding="utf-8"))
    
    def add_meta_info(self, key, value):
        self.init()
        if self.func_add_meta_info is not None:
            self.func_add_meta_info(bytes(key, encoding="utf-8"), bytes(value, encoding="utf-8"))
    
    def get_prof_path(self):
        self.init()
        if self.func_get_prof_path is None:
            return ""
        result = self.func_get_prof_path()
        if result:
            return result.decode("utf-8")
        return ""
    
    def is_torch_profiler_enable(self, profiler_level):
        self.init()
        if self.func_get_torch_profiler_enable is None or self.func_is_enable is None:
            return False
        return self.func_get_torch_profiler_enable() and self.func_is_enable(profiler_level)

    def get_acl_task_time_level(self):
        self.init()
        if self.func_get_acl_task_time_level is None:
            return "L0"
        result = self.func_get_acl_task_time_level()
        if result:
            return result.decode("utf-8")
        return "L0"

    def get_acl_prof_aicore_metrics(self):
        self.init()
        if self.func_get_acl_prof_aicore_metrics is None:
            return -1
        return self.func_get_acl_prof_aicore_metrics()

    def get_torch_prof_step_num(self):
        self.init()
        if self.func_get_torch_prof_step_num is None:
            return 0
        return self.func_get_torch_prof_step_num()

    def is_torch_prof_stack(self):
        self.init()
        if self.func_get_torch_prof_stack is None:
            return False
        return self.func_get_torch_prof_stack()

    def is_torch_prof_modules(self):
        self.init()
        if self.func_get_torch_prof_modules is None:
            return False
        return self.func_get_torch_prof_modules()

service_profiler = LibServiceProfiler()
