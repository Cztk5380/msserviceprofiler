# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import ctypes
from ms_service_profiler.utils.file_open_check import get_valid_lib_path


class LibServiceProfiler:
    lib_service_profiler = None

    def __init__(self) -> None:
        so_name = "libms_service_profiler.so"
        fp = get_valid_lib_path(so_name)

        if not fp:
            self.lib = None
            return

        try:
            self.lib = ctypes.cdll.LoadLibrary(fp)
        except Exception:
            self.lib = None

        self.func_start_span = None
        self.func_end_span = None
        self.func_mark_span_attr = None
        self.func_mark_event = None
        self.func_start_service_profiler = None
        self.func_stop_service_profiler = None
        self.func_is_enable = None
        self.func_add_meta_info = None
        self.func_is_valid_dommain = None

        if self.lib is not None:
            self.func_start_span_with_name = self.lib.StartSpanWithName
            self.func_start_span_with_name.argtypes = (ctypes.c_char_p, )
            self.func_start_span_with_name.restype = ctypes.c_ulonglong

            self.func_end_span = self.lib.EndSpan
            self.func_end_span.argtypes = (ctypes.c_ulonglong,)
            self.func_mark_span_attr = self.lib.MarkSpanAttr
            self.func_mark_span_attr.argtypes = (ctypes.c_char_p, ctypes.c_ulonglong)
            self.func_mark_event = self.lib.MarkEvent
            self.func_mark_event.argtypes = (ctypes.c_char_p,)
            self.func_start_service_profiler = self.lib.StartServerProfiler
            self.func_stop_service_profiler = self.lib.StopServerProfiler
            self.func_is_enable = self.lib.IsEnable
            self.func_is_enable.argtypes = (ctypes.c_ulong,)
            self.func_is_enable.restype = ctypes.c_bool
            
            if hasattr(self.lib, "IsValidDomain"):
                self.func_is_valid_dommain = self.lib.IsValidDomain
                self.func_is_valid_dommain.argtypes = (ctypes.c_char_p,)
                self.func_is_valid_dommain.restype = ctypes.c_bool
            
            if hasattr(self.lib, "AddMetaInfo"):
                self.func_add_meta_info = self.lib.AddMetaInfo
                self.func_add_meta_info.argtypes = (ctypes.c_char_p, ctypes.c_char_p)


    def start_span(self, name=None):
        if self.func_start_span_with_name is None:
            return 0
        msg = "" if name is None else name
        return self.func_start_span_with_name(bytes(msg, encoding="utf-8"))

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
        if self.func_start_service_profiler is not None:
            self.func_start_service_profiler()

    def stop_profiler(self):
        if self.func_stop_service_profiler is not None:
            self.func_stop_service_profiler()

    def is_enable(self, profiler_level):
        if self.func_is_enable is None:
            return False
        return self.func_is_enable(profiler_level)

    def is_domain_enable(self, domain_name):
        if self.func_is_valid_dommain is None:
            return True
        return self.func_is_valid_dommain(bytes(domain_name, encoding="utf-8"))
    
    def add_meta_info(self, key, value):
        if self.func_add_meta_info is not None:
            self.func_add_meta_info(bytes(key, encoding="utf-8"), bytes(value, encoding="utf-8"))


service_profiler = LibServiceProfiler()
