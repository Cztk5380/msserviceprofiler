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

import importlib
import os
import shutil
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from ms_service_profiler.patcher.core.config_loader import (
    _parse_symbol_path,
    _build_hook_points,
    _resolve_handler_func,
    ConfigLoader,
    DynamicHooker
)


class TestParseSymbolPath:
    """测试_parse_symbol_path函数"""

    @pytest.mark.parametrize("symbol_path,expected", [
        ("my_module.path:MyClass.my_method", ("my_module.path", "my_method", "MyClass")),
        ("my_module.path:my_function", ("my_module.path", "my_function", None)),
        ("module.path.ClassName.methodName", ("", "", None)),
        ("", ("", "", None)),
        ("my_module.path:MyClass.method.name.with.dots", ("my_module.path", "method.name.with.dots", "MyClass")),
    ])
    def test_parse_symbol_path(self, symbol_path, expected):
        assert _parse_symbol_path(symbol_path) == expected


class TestBuildHookPoints:
    """测试_build_hook_points函数"""

    @pytest.mark.parametrize("module_path,method_name,class_name,expected", [
        ("my_module.path", "my_method", "MyClass", [("my_module.path", "MyClass.my_method")]),
        ("my_module.path", "my_function", None, [("my_module.path", "my_function")]),
        ("", "", None, [("", "")]),
    ])
    def test_build_hook_points(self, module_path, method_name, class_name, expected):
        assert _build_hook_points(module_path, method_name, class_name) == expected


class TestResolveHandlerFunc:
    """测试_resolve_handler_func函数"""

    def test_resolve_handler_func_import_success_returns_handler(self):
        mock_module = MagicMock()
        mock_handler = MagicMock()
        mock_module.my_handler = mock_handler
        with patch("importlib.import_module", return_value=mock_module):
            result = _resolve_handler_func({"handler": "my_module.handlers:my_handler"}, "my_method")
            assert result == mock_handler
            importlib.import_module.assert_called_once_with("my_module.handlers")

    def test_resolve_handler_func_import_fails_returns_default(self):
        with patch("importlib.import_module", side_effect=ImportError("No module")):
            with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
                default_h = MagicMock()
                m.return_value = default_h
                result = _resolve_handler_func(
                    {"handler": "x:y", "domain": "TestDomain", "name": "custom_name"}, "my_method"
                )
                assert result == default_h
                m.assert_called_once_with(domain="TestDomain", name="custom_name", attributes=None)

    def test_resolve_handler_func_not_callable_returns_default(self):
        mock_module = MagicMock()
        mock_module.my_handler = "not_a_function"
        with patch("importlib.import_module", return_value=mock_module):
            with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
                default_h = MagicMock()
                m.return_value = default_h
                result = _resolve_handler_func(
                    {"handler": "my_module.handlers:my_handler", "domain": "TestDomain"}, "my_method"
                )
                assert result == default_h
                m.assert_called_once_with(domain="TestDomain", name="my_method", attributes=None)

    def test_resolve_handler_func_no_handler_returns_default(self):
        with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
            default_h = MagicMock()
            m.return_value = default_h
            result = _resolve_handler_func(
                {"domain": "TestDomain", "name": "test_name", "attributes": {"attr1": "value1"}}, "my_method"
            )
            assert result == default_h
            m.assert_called_once_with(domain="TestDomain", name="test_name", attributes={"attr1": "value1"})

    def test_resolve_handler_func_invalid_format_returns_default(self):
        with patch("ms_service_profiler.patcher.core.config_loader.make_default_time_hook") as m:
            default_h = MagicMock()
            m.return_value = default_h
            result = _resolve_handler_func(
                {"handler": "invalid_format_without_colon", "domain": "TestDomain"}, "my_method"
            )
            assert result == default_h
            m.assert_called_once_with(domain="TestDomain", name="my_method", attributes=None)


class TestConfigLoader:
    """测试ConfigLoader类"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.yaml")
        self.loader = ConfigLoader(self.config_path)
    
    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_config(self, content):
        with open(self.config_path, 'w') as f:
            f.write(content)

    def test_config_loader_init_stores_path(self):
        loader = ConfigLoader("/path/to/config.yaml")
        assert loader._config_path == "/path/to/config.yaml"

    def test_load_valid_yaml_returns_handler_dict(self):
        self._create_test_config("- symbol: a\n  domain: D\n")
        raw = [
            {"symbol": "module.path:ClassName.method_name", "domain": "TestDomain", "name": "test_name",
             "min_version": "1.0.0", "max_version": "2.0.0", "attributes": {"attr1": "value1", "attr2": "value2"}},
            {"symbol": "another.module:function_name", "handler": "custom.handlers:my_handler"},
        ]
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw):
            with patch("ms_service_profiler.patcher.core.config_loader.DynamicHooker") as MockDH:
                h1, h2 = MagicMock(), MagicMock()
                MockDH.side_effect = [h1, h2]
                result = self.loader.load()
        assert isinstance(result, dict)
        assert result["module.path:ClassName.method_name"] == [h1]
        assert result["another.module:function_name"] == [h2]
                
    def test_load_multiple_handlers_same_symbol_returns_all(self):
        self._create_test_config("")
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config") as mock_yaml:
            mock_yaml.return_value = [
                {"symbol": "module.path:ClassName.method_name", "domain": "FirstHandler"},
                {"symbol": "module.path:ClassName.method_name", "domain": "SecondHandler"},
            ]
            with patch("ms_service_profiler.patcher.core.config_loader.DynamicHooker") as MockDH:
                h1, h2 = MagicMock(), MagicMock()
                MockDH.side_effect = [h1, h2]
                result = self.loader.load()
        assert result["module.path:ClassName.method_name"] == [h1, h2]

    @pytest.mark.parametrize("yaml_return", [[], None, {"key": "value"}])
    def test_load_empty_or_invalid_returns_empty_dict(self, yaml_return):
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=yaml_return):
            assert self.loader.load() == {}
    @pytest.mark.parametrize("raw_config", [
        [{"domain": "TestDomain", "name": "test"}, {"symbol": "module.path:ClassName.method_name", "domain": "Valid"}],
        [{"symbol": "invalid_format_without_colon"}, {"symbol": "module.path:ClassName.method_name", "domain": "Valid"}],
    ])
    def test_load_skips_invalid_items(self, raw_config):
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config", return_value=raw_config):
            with patch("ms_service_profiler.patcher.core.config_loader.DynamicHooker") as MockDH:
                MockDH.return_value = MagicMock()
                result = self.loader.load()
        assert len(result) == 1
        assert "module.path:ClassName.method_name" in result
    def test_load_real_yaml_parses_correctly(self):
        self._create_test_config(
            '- symbol: "sglang.srt.managers.scheduler:Scheduler.get_next_batch_to_run"\n  domain: "Schedule"\n'
            '- symbol: "sglang.srt.managers.scheduler:Scheduler.run_batch"\n  domain: "ModelExecute"\n'
        )
        with patch("ms_service_profiler.patcher.core.config_loader.DynamicHooker") as MockDH:
            h1, h2 = MagicMock(), MagicMock()
            MockDH.side_effect = [h1, h2]
            result = self.loader.load()
        assert len(result) == 2
        assert "sglang.srt.managers.scheduler:Scheduler.get_next_batch_to_run" in result
        assert "sglang.srt.managers.scheduler:Scheduler.run_batch" in result

    def test_load_logs_debug(self):
        with patch("ms_service_profiler.patcher.core.config_loader.load_yaml_config") as mock_yaml:
            mock_yaml.return_value = [{"symbol": "module.path:ClassName.method_name", "domain": "TestDomain"}]
            with patch("ms_service_profiler.patcher.core.config_loader.DynamicHooker"):
                with patch("ms_service_profiler.patcher.core.config_loader.logger") as mock_logger:
                    self.loader.load()
                    mock_logger.debug.assert_called()
                    assert self.config_path in mock_logger.debug.call_args[0][0]
