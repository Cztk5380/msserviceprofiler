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

"""
C++ Service Profiler 库的 Python 绑定。

该模块负责：
- 加载 C++ 库 (libms_service_profiler.so)
- 封装 C++ 函数调用
- 统一管理 Profiler 回调（C++ 调用 mstx，mstx 再调用各 Profiler）

回调架构：
    C++ StartProfiler → mstx._on_cpp_start() → 遍历调用所有注册的 start 回调
    C++ StopProfiler  → mstx._on_cpp_stop()  → 遍历调用所有注册的 stop 回调
"""

import ctypes
from typing import Callable, List

from ms_service_profiler.utils.file_open_check import get_valid_lib_path


class ProfilerCallbackResult:
    """回调注册结果。"""

    # 注册模式
    DYNAMIC = "dynamic"      # 动态模式：C++ 回调注册成功
    LEGACY = "legacy"        # Legacy 模式：C++ 不支持，需要立即启用 hooks

    def __init__(self, mode: str, message: str = ""):
        self.mode = mode
        self.message = message

    @property
    def is_dynamic(self) -> bool:
        return self.mode == self.DYNAMIC

    @property
    def is_legacy(self) -> bool:
        return self.mode == self.LEGACY


class LibServiceProfiler:
    """C++ Service Profiler 库的 Python 封装。"""

    lib_service_profiler = None

    def __init__(self) -> None:
        self.is_initialized = False
        self.lib = None

        # 基础函数
        self.func_start_span_with_name = None
        self.func_end_span = None
        self.func_span_end_ex = None
        self.func_mark_span_attr = None
        self.func_mark_event = None
        self.func_mark_event_ex = None
        self.func_start_service_profiler = None
        self.func_stop_service_profiler = None
        self.func_is_enable = None
        self.func_is_valid_dommain = None
        self.func_add_meta_info = None

        # Profiler 配置函数
        self.func_get_prof_path = None
        self.func_get_acl_task_time_level = None
        self.func_get_acl_prof_aicore_metrics = None
        self.func_get_torch_prof_step_num = None
        self.func_get_torch_prof_stack = None
        self.func_get_torch_prof_modules = None
        self.func_get_torch_profiler_enable = None

        # C++ 回调注册函数
        self._func_register_start_callback = None
        self._func_register_stop_callback = None

        # Python 侧回调列表（支持多个 Profiler 注册）
        self._start_callbacks: List[Callable[[], None]] = []
        self._stop_callbacks: List[Callable[[], None]] = []

        # C 回调引用（防止被垃圾回收）
        self._c_callback_refs = []

        # 是否已注册到 C++
        self._cpp_callbacks_registered = False

    def init(self) -> None:
        """初始化 C++ 库。"""
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
            return

        if self.lib is not None:
            self._init_basic_funcs()
            self._init_config_funcs()
            self._init_callback_funcs()

    def _init_basic_funcs(self):
        """初始化基础函数。"""
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
            self.func_mark_event_ex.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p)
        except AttributeError:
            self.func_mark_event_ex = None

        try:
            self.func_span_end_ex = self.lib.SpanEndEx
            self.func_span_end_ex.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulonglong)
        except AttributeError:
            self.func_span_end_ex = None

        self.func_start_service_profiler = self.lib.StartServerProfiler
        self.func_stop_service_profiler = self.lib.StopServerProfiler

        self.func_is_enable = self.lib.IsEnable
        self.func_is_enable.argtypes = (ctypes.c_ulong,)
        self.func_is_enable.restype = ctypes.c_bool

    def _init_config_funcs(self):
        """初始化配置相关函数。"""
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

        if hasattr(self.lib, "SetProfilerCurrentStep"):
            self.func_set_profiler_current_step = self.lib.SetProfilerCurrentStep
            self.func_set_profiler_current_step.argtypes = (ctypes.c_int,)
            self.func_set_profiler_current_step.restype = None

    def _init_callback_funcs(self):
        """初始化 C++ 回调注册函数。"""
        if hasattr(self.lib, "RegisterProfilerStartCallback"):
            self._func_register_start_callback = self.lib.RegisterProfilerStartCallback
            self._func_register_start_callback.argtypes = (ctypes.CFUNCTYPE(None),)

        if hasattr(self.lib, "RegisterProfilerStopCallback"):
            self._func_register_stop_callback = self.lib.RegisterProfilerStopCallback
            self._func_register_stop_callback.argtypes = (ctypes.CFUNCTYPE(None),)

    # -------------------------------------------------------------------------
    # C++ 回调处理（内部方法）
    # -------------------------------------------------------------------------

    def _on_cpp_start(self) -> None:
        """C++ StartProfiler 时调用，遍历调用所有注册的 start 回调。"""
        for callback in self._start_callbacks:
            try:
                callback()
            except Exception:
                pass  # 单个回调失败不影响其他

    def _on_cpp_stop(self) -> None:
        """C++ StopProfiler 时调用，遍历调用所有注册的 stop 回调。"""
        for callback in self._stop_callbacks:
            try:
                callback()
            except Exception:
                pass  # 单个回调失败不影响其他

    def _ensure_cpp_callbacks_registered(self) -> bool:
        """确保 mstx 的回调已注册到 C++（只注册一次）。

        Returns:
            bool: 是否支持动态回调
        """
        if self._cpp_callbacks_registered:
            return True

        self.init()

        if self.lib is None:
            return False

        if self._func_register_start_callback is None or self._func_register_stop_callback is None:
            return False

        # 创建 C 回调
        c_start = ctypes.CFUNCTYPE(None)(self._on_cpp_start)
        c_stop = ctypes.CFUNCTYPE(None)(self._on_cpp_stop)

        # 保存引用防止垃圾回收
        self._c_callback_refs.append(c_start)
        self._c_callback_refs.append(c_stop)

        # 注册到 C++
        self._func_register_start_callback(c_start)
        self._func_register_stop_callback(c_stop)

        self._cpp_callbacks_registered = True
        return True

    # -------------------------------------------------------------------------
    # Profiler 回调注册接口
    # -------------------------------------------------------------------------

    def register_profiler_start_callback(self, callback: Callable[[], None]) -> ProfilerCallbackResult:
        """注册 Profiler 启动回调。

        Args:
            callback: Profiler 启动时的回调函数

        Returns:
            ProfilerCallbackResult: 注册结果
        """
        # 添加到回调列表
        self._start_callbacks.append(callback)

        # 确保 mstx 回调已注册到 C++
        if self._ensure_cpp_callbacks_registered():
            return ProfilerCallbackResult(
                ProfilerCallbackResult.DYNAMIC,
                "Callback registered successfully"
            )
        else:
            return ProfilerCallbackResult(
                ProfilerCallbackResult.LEGACY,
                "C++ library does not support dynamic callbacks"
            )

    def register_profiler_stop_callback(self, callback: Callable[[], None]) -> ProfilerCallbackResult:
        """注册 Profiler 停止回调。

        Args:
            callback: Profiler 停止时的回调函数

        Returns:
            ProfilerCallbackResult: 注册结果
        """
        # 添加到回调列表
        self._stop_callbacks.append(callback)

        # 确保 mstx 回调已注册到 C++
        if self._ensure_cpp_callbacks_registered():
            return ProfilerCallbackResult(
                ProfilerCallbackResult.DYNAMIC,
                "Callback registered successfully"
            )
        else:
            return ProfilerCallbackResult(
                ProfilerCallbackResult.LEGACY,
                "C++ library does not support dynamic callbacks"
            )

    def supports_dynamic_callbacks(self) -> bool:
        """检查是否支持动态回调。

        Returns:
            bool: 是否支持
        """
        self.init()
        return (self.lib is not None and
                self._func_register_start_callback is not None and
                self._func_register_stop_callback is not None)

    # -------------------------------------------------------------------------
    # Span/Event 相关方法
    # -------------------------------------------------------------------------

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
        """记录增强事件。"""
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
            if self.func_mark_span_attr is not None:
                import json
                extra = json.dumps({
                    "name": name,
                    "domain": domain,
                    "msg": msg
                }, ensure_ascii=False)
                self.func_mark_span_attr(bytes(extra, "utf-8"), span_handle)
            self.func_end_span(span_handle)

    # -------------------------------------------------------------------------
    # Profiler 控制方法
    # -------------------------------------------------------------------------

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

    def set_profiler_current_step(self, step: int) -> None:
        """设置当前 Profiler 步数，用于触发 step-based 自动停止。

        Args:
            step (int): 当前训练/推理步数
        """
        self.init()
        if self.func_set_profiler_current_step is not None:
            self.func_set_profiler_current_step(ctypes.c_int(step))


# 全局单例
service_profiler = LibServiceProfiler()
