# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
from unittest.mock import patch, MagicMock
import ctypes

from ms_service_profiler.mstx import LibServiceProfiler


class TestLibServiceProfiler(unittest.TestCase):

    @patch("ms_service_profiler.utils.file_open_check.get_valid_lib_path")
    def setUp(self, mock_get_valid_lib_path):
        # 模拟get_valid_lib_path返回一个有效的路径
        mock_get_valid_lib_path.return_value = "/path/to/libms_service_profiler.so"
        self.service_profiler = LibServiceProfiler()

    @patch("ms_service_profiler.utils.file_open_check.get_valid_lib_path")
    @patch("ctypes.cdll.LoadLibrary")
    def test_init_with_valid_lib_path(self, mock_load_library, mock_get_valid_lib_path):
        # 模拟get_valid_lib_path返回一个有效的路径
        mock_get_valid_lib_path.return_value = "/path/to/libms_service_profiler.so"
        # 模拟LoadLibrary返回一个有效的库对象
        mock_load_library.return_value = MagicMock()

        # 初始化LibServiceProfiler
        profiler = LibServiceProfiler()

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
        self.service_profiler.func_add_meta_info.assert_called_once_with("key", "value")


if __name__ == '__main__':
    unittest.main()