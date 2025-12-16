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

import pytest
from argparse import ArgumentTypeError

from ms_service_profiler.analyze import check_input_path_valid


@pytest.fixture
def setup_test_directory(tmp_path):
    # 创建一个临时目录用于测试
    test_dir = tmp_path / "test_directory"
    test_dir.mkdir()
    return test_dir


def test_valid_directory(setup_test_directory):
    # 测试合法的目录路径
    path = setup_test_directory
    result = check_input_path_valid(str(path))
    assert result == str(path)


def test_invalid_directory(setup_test_directory):
    # 测试非法目录路径（路径不存在）
    path = setup_test_directory / "nonexistent"
    with pytest.raises(ArgumentTypeError) as context:
        check_input_path_valid(str(path))
    assert f"Path is not a valid directory: {path}" in str(context.value)


def test_not_a_directory(setup_test_directory):
    # 测试路径不是目录（是文件）
    file_path = setup_test_directory / "test_file.txt"
    file_path.write_text("test content")
    with pytest.raises(ArgumentTypeError) as context:
        check_input_path_valid(str(file_path))
    assert f"Path is not a valid directory: {file_path}" in str(context.value)


def test_file_stat_exception(setup_test_directory):
    # 测试路径过长的情况
    long_path = setup_test_directory / ("a" * 4097)
    with pytest.raises(ArgumentTypeError) as context:
        check_input_path_valid(str(long_path))
    assert f"input path:{long_path} is illegal. Please check." in str(context.value)