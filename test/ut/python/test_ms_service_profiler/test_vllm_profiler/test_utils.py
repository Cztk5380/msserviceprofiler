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

import os
import sys
import importlib
import tempfile
import shutil
from unittest.mock import Mock, patch

import pytest

from ms_service_profiler.patcher.core.utils import (
    load_yaml_config, 
    parse_version_tuple
)


@pytest.fixture
def temp_config_dir():
    """创建临时配置目录的 fixture"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_yaml_content():
    """提供示例 YAML 内容的 fixture"""
    return """
- symbol: "module1:Class1.method1"
  handler: "handlers:time_hook"
  domain: "TestDomain"
- symbol: "module2:function2"
  handler: "timer"
  attributes:
    - name: "input_length"
      expr: "len(kwargs['input_ids'])"
"""


@pytest.fixture
def mock_distribution():
    """提供模拟 distribution 的 fixture"""
    mock_dist = Mock()
    mock_dist.locate_file.return_value = "/fake/path/vllm_ascend"
    return mock_dist


class TestLoadYamlConfig:
    """测试 load_yaml_config 函数"""
    
    @staticmethod
    def test_load_yaml_config_success(temp_config_dir, sample_yaml_content):
        """测试成功加载 YAML 配置"""
        config_file = os.path.join(temp_config_dir, 'test_config.yaml')
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(sample_yaml_content)
        
        result = load_yaml_config(config_file)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]['symbol'] == 'module1:Class1.method1'
        assert result[1]['symbol'] == 'module2:function2'

    @staticmethod
    def test_load_yaml_config_pyyaml_not_installed():
        """测试 PyYAML 未安装的情况"""
        with patch.dict('sys.modules', {'yaml': None}):
            # 重新导入以应用模拟（此处仅保留 importlib 用于 reload）
            if 'ms_service_profiler.patcher.core.utils' in sys.modules:
                importlib.reload(sys.modules['ms_service_profiler.patcher.core.utils'])
            result = load_yaml_config('/fake/path.yaml')
            assert result is None

    @staticmethod
    def test_load_yaml_config_file_not_found():
        """测试配置文件不存在的情况"""
        result = load_yaml_config('/nonexistent/path.yaml')
        
        assert result is None

    @staticmethod
    def test_load_yaml_config_invalid_yaml(temp_config_dir):
        """测试无效的 YAML 内容"""
        config_file = os.path.join(temp_config_dir, 'invalid.yaml')
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("invalid: yaml: content: [unclosed bracket")
        
        result = load_yaml_config(config_file)
        
        assert result is None

    @staticmethod
    def test_load_yaml_config_not_list(temp_config_dir):
        """测试 YAML 内容不是列表的情况"""
        config_file = os.path.join(temp_config_dir, 'not_list.yaml')
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("symbol: test\nhandler: timer")
        
        result = load_yaml_config(config_file)
        
        # 应该返回空列表而不是 None
        assert result == []

    @staticmethod
    def test_load_yaml_config_empty_file(temp_config_dir):
        """测试空配置文件"""
        config_file = os.path.join(temp_config_dir, 'empty.yaml')
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("")
        
        result = load_yaml_config(config_file)
        
        # 空文件应该返回 None（yaml.safe_load 返回 None）
        assert result is None

    @staticmethod
    def test_load_yaml_config_encoding_error(temp_config_dir):
        """测试编码错误的情况"""
        config_file = os.path.join(temp_config_dir, 'encoding_error.yaml')
        # 写入一些二进制数据模拟编码错误
        with open(config_file, 'wb') as f:
            f.write(b'\xff\xfeinvalid encoding')
        
        result = load_yaml_config(config_file)
        
        assert result is None


class TestParseVersionTuple:
    """测试 parse_version_tuple 函数"""
    
    @staticmethod
    @pytest.mark.parametrize("version_str,expected", [
        ("1.2.3", (1, 2, 3)),
        ("0.9.2", (0, 9, 2)),
        ("2.0.0", (2, 0, 0)),
        ("1.2.3+dev", (1, 2, 3)),  # 包含 + 的版本
        ("1.2.3-beta", (1, 2, 3)),  # 包含 - 的版本
        ("1.2", (1, 2, 0)),  # 缺少 patch 版本
        ("1", (1, 0, 0)),  # 只有 major 版本
        ("0.9.2+cpu", (0, 9, 2)),  # 包含 + 和其他标识
        ("1.2.3.4", (1, 2, 3)),  # 超过三个部分
    ])
    def test_parse_version_tuple_valid(version_str, expected):
        """测试解析有效的版本字符串"""
        result = parse_version_tuple(version_str)
        assert result == expected

    @staticmethod
    @pytest.mark.parametrize("version_str,expected", [
        ("1.2.a", (1, 2, 0)),  # 包含非数字字符
        ("a.b.c", (0, 0, 0)),  # 全部为非数字
        ("", (0, 0, 0)),  # 空字符串
        (".", (0, 0, 0)),  # 只有点
    ])
    def test_parse_version_tuple_invalid(version_str, expected):
        """测试解析无效的版本字符串"""
        result = parse_version_tuple(version_str)
        assert result == expected

    @staticmethod
    def test_parse_version_tuple_none_input():
        """测试 None 输入（虽然函数签名是 str，但测试边界情况）"""
        # 注意：函数期望字符串输入，但测试意外情况
        result = parse_version_tuple(None)
        # 根据实现，可能会抛出异常或返回默认值
        # 这里我们期望它能处理异常


class TestIntegration:
    """集成测试"""

    @staticmethod
    def test_version_parsing_integration():
        """测试版本解析的集成"""
        test_versions = [
            ("0.9.2", (0, 9, 2)),
            ("1.2.3+dev", (1, 2, 3)),
            ("2.0", (2, 0, 0)),
        ]
        
        for version_str, expected in test_versions:
            result = parse_version_tuple(version_str)
            assert result == expected
            
            # 测试版本比较（auto_detect_v1_default 中的逻辑）
            use_v1 = result >= (0, 9, 2)
            expected_use_v1 = version_str not in ["0.9.1", "0.8.0"]  # 这些应该返回 False
            assert use_v1 == expected_use_v1


class TestEdgeCases:
    """边界情况测试"""

    @staticmethod
    def test_load_yaml_config_large_file(temp_config_dir):
        """测试大文件加载（如果有内存限制需要考虑）"""
        config_file = os.path.join(temp_config_dir, 'large.yaml')
        
        # 创建一个大但不至于耗尽内存的 YAML 文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("- symbol: test\n  handler: timer\n")
            # 添加一些重复内容使文件变大但保持有效
            for i in range(1000):
                f.write(f"- symbol: test{i}\n  handler: timer\n")
        
        result = load_yaml_config(config_file)
        
        assert isinstance(result, list)
        assert len(result) == 1001

    @staticmethod
    def test_parse_version_tuple_very_long_version():
        """测试非常长的版本字符串"""
        long_version = "1." + "9." * 100 + "0"
        result = parse_version_tuple(long_version)
        
        # 应该只取前三个部分
        assert result == (1, 9, 9)
