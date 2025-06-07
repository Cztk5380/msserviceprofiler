# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock
from argparse import ArgumentTypeError

from ms_service_profiler.analyze import check_input_path_valid



class TestCheckInputPathValid(unittest.TestCase):
    def setUp(self):
        # 创建一个临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()


    def tearDown(self):
        # 删除临时目录
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


    def test_valid_directory(self):
        # 测试合法的目录路径
        path = self.temp_dir
        result = check_input_path_valid(path)
        self.assertEqual(result, path)
        self.tearDown()


    def test_invalid_directory(self):
        # 测试非法目录路径（路径不存在）
        path = os.path.join(self.temp_dir, "nonexistent")
        with self.assertRaises(ArgumentTypeError) as context:
            check_input_path_valid(path)
        self.assertIn(f"Path is not a valid directory: {path}", str(context.exception))
        self.tearDown()


    def test_not_a_directory(self):
        # 测试路径不是目录（是文件）
        path = os.path.join(self.temp_dir, "test_file.txt")
        with open(path, "w") as f:
            f.write("test content")
        with self.assertRaises(ArgumentTypeError) as context:
            check_input_path_valid(path)
        self.assertIn(f"Path is not a valid directory: {path}", str(context.exception))
        self.tearDown()


    @patch('ms_service_profiler.utils.file_open_check.FileStat')
    def test_file_stat_exception(self, mock_file_stat):
        path = "a" * 4097  # 构造一个长度超过 4096 的路径
        with self.assertRaises(ArgumentTypeError) as context:
            check_input_path_valid(path)
        self.assertIn(f"input path:{path} is illegal. Please check.", str(context.exception))
        self.tearDown()


if __name__ == '__main__':
    unittest.main()