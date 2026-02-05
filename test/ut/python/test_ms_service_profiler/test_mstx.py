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

import unittest
from unittest.mock import patch, MagicMock
import ctypes

from ms_service_profiler.mstx import LibServiceProfiler, ProfilerCallbackResult


class TestProfilerCallbackResult(unittest.TestCase):

    def test_callback_result_dynamic(self):
        result = ProfilerCallbackResult(ProfilerCallbackResult.DYNAMIC)
        self.assertEqual(result.mode, ProfilerCallbackResult.DYNAMIC)
        self.assertEqual(result.message, "")
        self.assertTrue(result.is_dynamic)
        self.assertFalse(result.is_legacy)

    def test_callback_result_legacy(self):
        result = ProfilerCallbackResult(ProfilerCallbackResult.LEGACY, "Legacy mode message")
        self.assertEqual(result.mode, ProfilerCallbackResult.LEGACY)
        self.assertEqual(result.message, "Legacy mode message")
        self.assertFalse(result.is_dynamic)
        self.assertTrue(result.is_legacy)

    def test_callback_result_dynamic_with_message(self):
        result = ProfilerCallbackResult(ProfilerCallbackResult.DYNAMIC, "Success message")
        self.assertTrue(result.is_dynamic)
        self.assertFalse(result.is_legacy)
        self.assertEqual(result.message, "Success message")


class TestLibServiceProfiler(unittest.TestCase):

    @patch("ms_service_profiler.utils.file_open_check.get_valid_lib_path")
    def setUp(self, mock_get_valid_lib_path=None):
        # 模拟get_valid_lib_path返回一个有效的路径
        if mock_get_valid_lib_path is not None:
            mock_get_valid_lib_path.return_value = "/path/to/libms_service_profiler.so"

        # 初始化 service_profiler 属性
        self.service_profiler = LibServiceProfiler()
        self.service_profiler.is_initialized = False

    @patch("ms_service_profiler.utils.file_open_check.get_valid_lib_path")
    @patch("ctypes.cdll.LoadLibrary")
    def test_init_with_valid_lib_path(self, mock_load_library, mock_get_valid_lib_path):
        # 模拟get_valid_lib_path返回一个有效的路径
        mock_get_valid_lib_path.return_value = "/path/to/libms_service_profiler.so"
        # 模拟LoadLibrary返回一个有效的库对象
        mock_load_library.return_value = MagicMock()

        # 初始化LibServiceProfiler
        profiler = LibServiceProfiler()
        profiler.init()

        # 检查lib是否被正确加载
        self.assertIsNotNone(profiler.lib)

    @patch("ms_service_profiler.utils.file_open_check.get_valid_lib_path")
    def test_init_with_empty_lib_path(self, mock_get_valid_lib_path):
        # 模拟get_valid_lib_path返回空字符串
        mock_get_valid_lib_path.return_value = ""
        profiler = LibServiceProfiler()
        self.assertIsNone(profiler.lib)

    @patch("ms_service_profiler.utils.file_open_check.get_valid_lib_path")
    def test_init_with_none_lib_path(self, mock_get_valid_lib_path):
        # 模拟get_valid_lib_path返回None
        mock_get_valid_lib_path.return_value = None
        profiler = LibServiceProfiler()
        self.assertIsNone(profiler.lib)

    @patch("ms_service_profiler.utils.file_open_check.get_valid_lib_path")
    def test_init_with_load_library_error(self, mock_get_valid_lib_path):
        # 模拟get_valid_lib_path返回一个有效的路径，但加载库时抛出异常
        mock_get_valid_lib_path.return_value = "/path/to/libms_service_profiler.so"
        with patch("ctypes.cdll.LoadLibrary", side_effect=Exception("Library load error")):
            profiler = LibServiceProfiler()
            self.assertIsNone(profiler.lib)

    def test_start_span(self):
        # 测试start_span方法
        self.service_profiler.func_start_span_with_name = MagicMock(return_value=12345)
        span_handle = self.service_profiler.start_span("test_span")
        self.assertEqual(span_handle, 12345)
        self.service_profiler.func_start_span_with_name.assert_called_once_with(b'test_span')

    def test_end_span(self):
        # 测试end_span方法
        self.service_profiler.func_end_span = MagicMock()
        self.service_profiler.end_span(12345)
        self.service_profiler.func_end_span.assert_called_once_with(12345)

    def test_mark_span_attr(self):
        # 测试mark_span_attr方法
        self.service_profiler.func_mark_span_attr = MagicMock()
        self.service_profiler.mark_span_attr("test_attr", 12345)
        self.service_profiler.func_mark_span_attr.assert_called_once_with(b'test_attr', 12345)

    def test_mark_event(self):
        # 测试mark_event方法
        self.service_profiler.func_mark_event = MagicMock()
        self.service_profiler.mark_event("test_event")
        self.service_profiler.func_mark_event.assert_called_once_with(b'test_event')

    def test_start_profiler(self):
        # 测试start_profiler方法
        self.service_profiler.func_start_service_profiler = MagicMock()
        self.service_profiler.start_profiler()
        self.service_profiler.func_start_service_profiler.assert_called_once()

    def test_stop_profiler(self):
        # 测试stop_profiler方法
        self.service_profiler.func_stop_service_profiler = MagicMock()
        self.service_profiler.stop_profiler()
        self.service_profiler.func_stop_service_profiler.assert_called_once()

    def test_is_enable(self):
        # 测试is_enable方法
        self.service_profiler.func_is_enable = MagicMock(return_value=True)
        result = self.service_profiler.is_enable(1)
        self.assertTrue(result)
        self.service_profiler.func_is_enable.assert_called_once_with(1)

    def test_add_meta_info(self):
        # 测试add_meta_info方法
        self.service_profiler.func_add_meta_info = MagicMock()
        self.service_profiler.add_meta_info("key", "value")
        self.service_profiler.func_add_meta_info.assert_called_once_with(b"key", b"value")

    def test_mark_event_ex_with_func(self):
        # 测试mark_event_ex方法（func_mark_event_ex可用）
        self.service_profiler.func_mark_event_ex = MagicMock()
        self.service_profiler.mark_event_ex("test_name", "test_domain", "test_msg")
        self.service_profiler.func_mark_event_ex.assert_called_once_with(
            b"test_name", b"test_domain", b"test_msg"
        )

    def test_mark_event_ex_fallback(self):
        # 测试mark_event_ex回退到func_mark_event
        self.service_profiler.func_mark_event_ex = None
        self.service_profiler.func_mark_event = MagicMock()
        import json
        self.service_profiler.mark_event_ex("test_name", "test_domain", "test_msg")
        self.service_profiler.func_mark_event.assert_called_once()
        call_args = self.service_profiler.func_mark_event.call_args[0][0]
        result = json.loads(call_args)
        self.assertEqual(result["name"], "test_name")
        self.assertEqual(result["domain"], "test_domain")
        self.assertEqual(result["msg"], "test_msg")

    def test_span_end_ex_with_func(self):
        # 测试span_end_ex方法（func_span_end_ex可用）
        self.service_profiler.func_span_end_ex = MagicMock()
        self.service_profiler.span_end_ex("test_name", "test_domain", "test_msg", 12345)
        self.service_profiler.func_span_end_ex.assert_called_once_with(
            b"test_name", b"test_domain", b"test_msg", 12345
        )

    def test_span_end_ex_fallback(self):
        # 测试span_end_ex回退逻辑
        self.service_profiler.func_span_end_ex = None
        self.service_profiler.func_end_span = MagicMock()
        self.service_profiler.func_mark_event = MagicMock()
        self.service_profiler.span_end_ex("test_name", "test_domain", "test_msg", 12345)
        self.service_profiler.func_end_span.assert_called_once_with(12345)
        self.service_profiler.func_mark_event.assert_called_once()
        import json
        call_args = self.service_profiler.func_mark_event.call_args[0][0]
        result = json.loads(call_args)
        self.assertEqual(result["type"], "span_end_fallback")
        self.assertEqual(result["name"], "test_name")

    def test_is_domain_enable(self):
        # 测试is_domain_enable方法
        self.service_profiler.func_is_valid_dommain = MagicMock(return_value=True)
        result = self.service_profiler.is_domain_enable("test_domain")
        self.assertTrue(result)
        self.service_profiler.func_is_valid_dommain.assert_called_once_with(b"test_domain")

    def test_is_domain_enable_no_func(self):
        # 测试is_domain_enable无函数时默认返回True
        self.service_profiler.func_is_valid_dommain = None
        result = self.service_profiler.is_domain_enable("test_domain")
        self.assertTrue(result)

    def test_get_prof_path(self):
        # 测试get_prof_path方法
        self.service_profiler.func_get_prof_path = MagicMock(return_value=b"/test/path")
        result = self.service_profiler.get_prof_path()
        self.assertEqual(result, "/test/path")

    def test_get_prof_path_empty(self):
        # 测试get_prof_path返回空
        self.service_profiler.func_get_prof_path = MagicMock(return_value=None)
        result = self.service_profiler.get_prof_path()
        self.assertEqual(result, "")

    def test_get_acl_task_time_level(self):
        # 测试get_acl_task_time_level方法
        self.service_profiler.func_get_acl_task_time_level = MagicMock(return_value=b"L1")
        result = self.service_profiler.get_acl_task_time_level()
        self.assertEqual(result, "L1")

    def test_get_acl_task_time_level_default(self):
        # 测试get_acl_task_time_level默认返回值
        self.service_profiler.func_get_acl_task_time_level = None
        result = self.service_profiler.get_acl_task_time_level()
        self.assertEqual(result, "L0")

    def test_get_acl_prof_aicore_metrics(self):
        # 测试get_acl_prof_aicore_metrics方法
        self.service_profiler.func_get_acl_prof_aicore_metrics = MagicMock(return_value=3)
        result = self.service_profiler.get_acl_prof_aicore_metrics()
        self.assertEqual(result, 3)

    def test_get_acl_prof_aicore_metrics_default(self):
        # 测试get_acl_prof_aicore_metrics默认返回值
        self.service_profiler.func_get_acl_prof_aicore_metrics = None
        result = self.service_profiler.get_acl_prof_aicore_metrics()
        self.assertEqual(result, -1)

    def test_get_torch_prof_step_num(self):
        # 测试get_torch_prof_step_num方法
        self.service_profiler.func_get_torch_prof_step_num = MagicMock(return_value=100)
        result = self.service_profiler.get_torch_prof_step_num()
        self.assertEqual(result, 100)

    def test_get_torch_prof_step_num_default(self):
        # 测试get_torch_prof_step_num默认返回值
        self.service_profiler.func_get_torch_prof_step_num = None
        result = self.service_profiler.get_torch_prof_step_num()
        self.assertEqual(result, 0)

    def test_is_torch_prof_stack(self):
        # 测试is_torch_prof_stack方法
        self.service_profiler.func_get_torch_prof_stack = MagicMock(return_value=True)
        result = self.service_profiler.is_torch_prof_stack()
        self.assertTrue(result)

    def test_is_torch_prof_stack_default(self):
        # 测试is_torch_prof_stack默认返回值
        self.service_profiler.func_get_torch_prof_stack = None
        result = self.service_profiler.is_torch_prof_stack()
        self.assertFalse(result)

    def test_is_torch_prof_modules(self):
        # 测试is_torch_prof_modules方法
        self.service_profiler.func_get_torch_prof_modules = MagicMock(return_value=True)
        result = self.service_profiler.is_torch_prof_modules()
        self.assertTrue(result)

    def test_is_torch_prof_modules_default(self):
        # 测试is_torch_prof_modules默认返回值
        self.service_profiler.func_get_torch_prof_modules = None
        result = self.service_profiler.is_torch_prof_modules()
        self.assertFalse(result)

    def test_is_torch_profiler_enable(self):
        # 测试is_torch_profiler_enable方法
        self.service_profiler.func_get_torch_profiler_enable = MagicMock(return_value=True)
        self.service_profiler.func_is_enable = MagicMock(return_value=True)
        result = self.service_profiler.is_torch_profiler_enable(10)
        self.assertTrue(result)

    def test_is_torch_profiler_enable_no_torch_func(self):
        # 测试is_torch_profiler_enable无torch函数时返回False
        self.service_profiler.func_get_torch_profiler_enable = None
        result = self.service_profiler.is_torch_profiler_enable(10)
        self.assertFalse(result)

    def test_is_torch_profiler_enable_disabled(self):
        # 测试is_torch_profiler_enable禁用时返回False
        self.service_profiler.func_get_torch_profiler_enable = MagicMock(return_value=True)
        self.service_profiler.func_is_enable = MagicMock(return_value=False)
        result = self.service_profiler.is_torch_profiler_enable(10)
        self.assertFalse(result)

    def test_start_span_with_none_name(self):
        # 测试start_span方法name为None
        self.service_profiler.func_start_span_with_name = MagicMock(return_value=12345)
        span_handle = self.service_profiler.start_span(None)
        self.assertEqual(span_handle, 12345)
        self.service_profiler.func_start_span_with_name.assert_called_once_with(b"")

    def test_start_span_no_func(self):
        # 测试start_span方法无函数时返回0
        self.service_profiler.func_start_span_with_name = None
        span_handle = self.service_profiler.start_span("test")
        self.assertEqual(span_handle, 0)

    def test_end_span_no_func(self):
        # 测试end_span方法无函数时不调用
        self.service_profiler.func_end_span = None
        self.service_profiler.end_span(12345)

    def test_mark_span_attr_no_func(self):
        # 测试mark_span_attr方法无函数时不调用
        self.service_profiler.func_mark_span_attr = None
        self.service_profiler.mark_span_attr("test_attr", 12345)

    def test_mark_event_no_func(self):
        # 测试mark_event方法无函数时不调用
        self.service_profiler.func_mark_event = None
        self.service_profiler.mark_event("test_event")

    def test_start_profiler_no_func(self):
        # 测试start_profiler方法无函数时不调用
        self.service_profiler.func_start_service_profiler = None
        self.service_profiler.start_profiler()

    def test_stop_profiler_no_func(self):
        # 测试stop_profiler方法无函数时不调用
        self.service_profiler.func_stop_service_profiler = None
        self.service_profiler.stop_profiler()

    def test_is_enable_no_func(self):
        # 测试is_enable方法无函数时返回False
        self.service_profiler.func_is_enable = None
        result = self.service_profiler.is_enable(1)
        self.assertFalse(result)

    def test_add_meta_info_no_func(self):
        # 测试add_meta_info方法无函数时不调用
        self.service_profiler.func_add_meta_info = None
        self.service_profiler.add_meta_info("key", "value")

    def test_supports_dynamic_callbacks_true(self):
        # 测试supports_dynamic_callbacks返回True
        self.service_profiler.init()
        self.service_profiler.lib = MagicMock()
        self.service_profiler._func_register_start_callback = MagicMock()
        self.service_profiler._func_register_stop_callback = MagicMock()
        result = self.service_profiler.supports_dynamic_callbacks()
        self.assertTrue(result)

    def test_supports_dynamic_callbacks_no_lib(self):
        # 测试supports_dynamic_callbacks无lib时返回False
        self.service_profiler.init()
        self.service_profiler.lib = None
        result = self.service_profiler.supports_dynamic_callbacks()
        self.assertFalse(result)

    def test_supports_dynamic_callbacks_no_register_funcs(self):
        # 测试supports_dynamic_callbacks无注册函数时返回False
        self.service_profiler.init()
        self.service_profiler.lib = MagicMock()
        self.service_profiler._func_register_start_callback = None
        self.service_profiler._func_register_stop_callback = None
        result = self.service_profiler.supports_dynamic_callbacks()
        self.assertFalse(result)

    def test_on_cpp_start(self):
        # 测试_on_cpp_start方法
        callback1 = MagicMock()
        callback2 = MagicMock()
        self.service_profiler._start_callbacks = [callback1, callback2]
        self.service_profiler._on_cpp_start()
        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_on_cpp_start_exception(self):
        # 测试_on_cpp_start方法中单个回调异常不影响其他
        callback1 = MagicMock(side_effect=Exception("Test error"))
        callback2 = MagicMock()
        self.service_profiler._start_callbacks = [callback1, callback2]
        self.service_profiler._on_cpp_start()
        callback2.assert_called_once()

    def test_on_cpp_stop(self):
        # 测试_on_cpp_stop方法
        callback1 = MagicMock()
        callback2 = MagicMock()
        self.service_profiler._stop_callbacks = [callback1, callback2]
        self.service_profiler._on_cpp_stop()
        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_on_cpp_stop_exception(self):
        # 测试_on_cpp_stop方法中单个回调异常不影响其他
        callback1 = MagicMock(side_effect=Exception("Test error"))
        callback2 = MagicMock()
        self.service_profiler._stop_callbacks = [callback1, callback2]
        self.service_profiler._on_cpp_stop()
        callback2.assert_called_once()

    def test_register_profiler_start_callback_dynamic(self):
        # 测试动态模式注册start回调
        callback = MagicMock()
        self.service_profiler.init()
        self.service_profiler.lib = MagicMock()
        self.service_profiler._func_register_start_callback = MagicMock()
        self.service_profiler._func_register_stop_callback = MagicMock()
        self.service_profiler._cpp_callbacks_registered = False
        result = self.service_profiler.register_profiler_start_callback(callback)
        self.assertEqual(result.mode, ProfilerCallbackResult.DYNAMIC)
        self.assertIn(callback, self.service_profiler._start_callbacks)

    def test_register_profiler_start_callback_legacy(self):
        # 测试legacy模式注册start回调
        callback = MagicMock()
        self.service_profiler._func_register_start_callback = None
        self.service_profiler._func_register_stop_callback = None
        result = self.service_profiler.register_profiler_start_callback(callback)
        self.assertEqual(result.mode, ProfilerCallbackResult.LEGACY)
        self.assertIn(callback, self.service_profiler._start_callbacks)

    def test_register_profiler_stop_callback_dynamic(self):
        # 测试动态模式注册stop回调
        callback = MagicMock()
        self.service_profiler.init()
        self.service_profiler.lib = MagicMock()
        self.service_profiler._func_register_start_callback = MagicMock()
        self.service_profiler._func_register_stop_callback = MagicMock()
        self.service_profiler._cpp_callbacks_registered = False
        result = self.service_profiler.register_profiler_stop_callback(callback)
        self.assertEqual(result.mode, ProfilerCallbackResult.DYNAMIC)
        self.assertIn(callback, self.service_profiler._stop_callbacks)

    def test_register_profiler_stop_callback_legacy(self):
        # 测试legacy模式注册stop回调
        callback = MagicMock()
        self.service_profiler._func_register_start_callback = None
        self.service_profiler._func_register_stop_callback = None
        result = self.service_profiler.register_profiler_stop_callback(callback)
        self.assertEqual(result.mode, ProfilerCallbackResult.LEGACY)
        self.assertIn(callback, self.service_profiler._stop_callbacks)

    def test_init_already_initialized(self):
        # 测试init已初始化时不重复初始化
        self.service_profiler.is_initialized = True
        self.service_profiler.init()
        self.assertTrue(self.service_profiler.is_initialized)


if __name__ == '__main__':
    unittest.main()