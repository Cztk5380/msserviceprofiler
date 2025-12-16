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

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ms_service_profiler.data_source.base_data_source import BaseDataSource


@patch('pathlib.Path.rglob')
def test_get_filepaths(mock_rglob):
    # 设置rglob方法的返回值
    mock_path1 = MagicMock()
    mock_path1.is_file.return_value = True
    mock_path1.name = 'file1.db'
    mock_path2 = MagicMock()
    mock_path2.is_file.return_value = True
    mock_path2.name = 'file2.db'
    mock_rglob.return_value = [mock_path1, mock_path2]

    # 定义文件模式映射
    file_pattern_map = {
        'group1': ('*.db', True),
        'group2': ('*.db', False)
    }

    # 调用get_filepaths方法
    result = BaseDataSource.get_filepaths('dummy_path', file_pattern_map)

    # 断言结果是一个字典
    assert isinstance(result, dict)
    assert len(result) == 2
    assert 'group1' in result
    assert 'group2' in result
    assert isinstance(result['group1'], list)
    assert isinstance(result['group2'], str)
    assert len(result['group1']) == 2
    assert result['group1'][0] == str(mock_path1)
    assert result['group1'][1] == str(mock_path2)
    assert result['group2'] == str(mock_path2) 