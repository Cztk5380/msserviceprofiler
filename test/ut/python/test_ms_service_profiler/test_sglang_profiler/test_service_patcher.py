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
import tempfile
from unittest.mock import Mock, patch, MagicMock, call
import pytest

from ms_service_profiler.patcher.sglang.service_patcher import SGLangPatcher


class TestSGLangPatcherInitialization:
    """测试 SGLangPatcher 初始化"""
    
    @staticmethod
    def test_initialization_given_new_instance_when_created_then_state_correct():
        """测试初始化状态"""
        # 测试：给定新实例，当创建时，状态正确
        patcher = SGLangPatcher()
        assert patcher._controller is None
        assert patcher._initialized is False
        # _hooks_applied 属性在 initialize 方法中设置，不在 __init__ 中


class TestFindConfigPath:
    """测试 _find_config_path 静态方法"""
    
    @staticmethod
    @pytest.mark.parametrize(
        "env_value, file_exists, expected_return, expected_log",
        [
            # 表格方式完整用例信息
            # | 环境变量值 | 文件是否存在 | 预期返回 | 预期日志 |
            ("/path/to/config.yaml", True, "/path/to/config.yaml", "Loading profiling symbols from env path"),
            ("/path/to/config.yml", True, "/path/to/config.yml", "Loading profiling symbols from env path"),
            ("/path/to/config.yaml", False, None, None),  # 文件不存在，不记录日志
        ]
    )
    def test_find_config_path_given_env_var_yaml_when_file_exists_then_return_path(
        env_value, file_exists, expected_return, expected_log, tmp_path
    ):
        """测试环境变量为YAML文件时的查找逻辑"""
        # 测试：给定环境变量为YAML文件，当文件存在时，返回路径
        with patch.dict(os.environ, {'PROFILING_SYMBOLS_PATH': env_value}):
            # 模拟文件检查：环境变量路径存在与否 + 本地配置文件不存在
            def isfile_side_effect(path):
                if path == env_value:
                    return file_exists
                # 本地配置文件不存在
                if 'service_profiling_symbols.yaml' in path:
                    return False
                return False
            
            with patch('os.path.isfile', side_effect=isfile_side_effect):
                with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.debug') as mock_debug:
                    result = SGLangPatcher._find_config_path()
                    
                    if expected_return:
                        assert result == expected_return
                        if expected_log:
                            # 检查是否包含预期的日志消息
                            debug_calls = [str(call) for call in mock_debug.call_args_list]
                            has_expected_log = any(expected_log in call for call in debug_calls)
                            assert has_expected_log, f"Expected log '{expected_log}' not found in {debug_calls}"
                    else:
                        assert result is None
    
    @staticmethod
    def test_find_config_path_given_env_var_not_yaml_when_path_invalid_then_log_warning(tmp_path):
        """测试环境变量为非YAML文件时的警告逻辑"""
        # 测试：给定环境变量为非YAML文件，当路径无效时，记录警告
        with patch.dict(os.environ, {'PROFILING_SYMBOLS_PATH': '/path/to/file.txt'}):
            # 模拟本地配置文件也不存在
            def isfile_side_effect(path):
                # 环境变量文件不存在（因为不是yaml文件，不会检查存在性）
                if 'service_profiling_symbols.yaml' in path:
                    return False
                return False
            
            with patch('os.path.isfile', side_effect=isfile_side_effect):
                with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.warning') as mock_warning:
                    result = SGLangPatcher._find_config_path()
                    # 由于环境变量不是yaml文件，应该记录警告，并且返回None（如果本地文件也不存在）
                    assert result is None
                    # 检查是否调用了警告日志
                    warning_calls = [str(call) for call in mock_warning.call_args_list]
                    has_warning = any('PROFILING_SYMBOLS_PATH is not a yaml file' in call for call in warning_calls)
                    assert has_warning, f"Expected warning not found in {warning_calls}"
    
    @staticmethod
    def test_find_config_path_given_no_env_var_when_local_file_exists_then_return_local_path():
        """测试无环境变量时查找本地配置文件"""
        # 测试：给定无环境变量，当本地文件存在时，返回本地路径
        with patch.dict(os.environ, {}, clear=True):
            # 模拟本地配置文件存在
            mock_local_path = '/mock/sglang/config/service_profiling_symbols.yaml'
            def isfile_side_effect(path):
                return path == mock_local_path
            
            with patch('os.path.isfile', side_effect=isfile_side_effect):
                with patch('os.path.dirname', return_value='/mock/sglang'):
                    with patch('os.path.join', return_value=mock_local_path):
                        with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.debug') as mock_debug:
                            result = SGLangPatcher._find_config_path()
                            
                            assert result == mock_local_path
                            # 验证调试日志被调用
                            debug_calls = [str(call) for call in mock_debug.call_args_list]
                            has_expected_log = any('Using SGLang profiling symbols from local project' in call for call in debug_calls)
                            assert has_expected_log, f"Expected log not found in {debug_calls}"
    
    @staticmethod
    def test_find_config_path_given_no_configs_when_all_missing_then_return_none():
        """测试所有配置文件都不存在的情况"""
        # 测试：给定无配置文件，当全部缺失时，返回None
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.isfile', return_value=False):
                result = SGLangPatcher._find_config_path()
                assert result is None


class TestLoadConfig:
    """测试 _load_config 方法"""
    
    @staticmethod
    def test_load_config_given_valid_path_when_load_succeeds_then_return_handlers():
        """测试成功加载配置文件（通过 ConfigLoader 返回 Handler 字典）"""
        mock_handlers = {'test:function': [MagicMock()]}
        with patch.object(SGLangPatcher, '_find_config_path', return_value='/mock/path.yaml'):
            with patch('ms_service_profiler.patcher.sglang.service_patcher.ConfigLoader') as MockConfigLoader:
                mock_loader_instance = MagicMock()
                mock_loader_instance.load_profiling.return_value = mock_handlers
                MockConfigLoader.return_value = mock_loader_instance
                with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.info') as mock_info:
                    patcher = SGLangPatcher()
                    result = patcher._load_config()
                    assert result == mock_handlers
                    MockConfigLoader.assert_called_once_with('/mock/path.yaml')
                    mock_loader_instance.load_profiling.assert_called_once()
                    mock_info.assert_called_once_with(
                        "Loading SGLang profiling symbols from: %s",
                        '/mock/path.yaml'
                    )
    
    @staticmethod
    def test_load_config_given_no_path_when_find_returns_none_then_log_warning():
        """测试找不到配置文件时的警告逻辑"""
        # 测试：给定无路径，当查找返回None时，记录警告
        with patch.object(SGLangPatcher, '_find_config_path', return_value=None):
            with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.warning') as mock_warning:
                patcher = SGLangPatcher()
                result = patcher._load_config()
                
                assert result is None
                mock_warning.assert_called_once_with("No SGLang profiling config found.")


class TestImportHandlers:
    """测试 _import_handlers 方法"""
    
    @staticmethod
    def test_import_handlers_given_valid_module_when_import_succeeds_then_log_debug():
        """测试成功导入handlers"""
        # 测试：给定有效模块，当导入成功时，记录调试日志
        patcher = SGLangPatcher()
        
        # 创建模拟的模块
        mock_module = Mock()
        sys.modules['ms_service_profiler.patcher.sglang.handlers'] = mock_module
        mock_module.scheduler_handlers = Mock()
        mock_module.request_handlers = Mock()
        mock_module.model_handlers = Mock()
        
        with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.debug') as mock_debug:
            patcher._import_handlers()
            
            mock_debug.assert_called_once_with(
                "Initializing service patcher with SGLang interface"
            )
        
        # 清理
        del sys.modules['ms_service_profiler.patcher.sglang.handlers']


class TestInitialize:
    """测试 initialize 方法"""
    
    @staticmethod
    def test_initialize_given_profiling_disabled_when_check_fails_then_return_false():
        """测试性能分析未启用时的初始化逻辑"""
        # 测试：给定性能分析未启用，当检查失败时，返回False
        patcher = SGLangPatcher()
        
        with patch('ms_service_profiler.patcher.sglang.service_patcher.check_profiling_enabled', 
                  return_value=False):
            result = patcher.initialize()
            
            assert result is False
            # 注意：原代码中没有设置 _initialized，所以这里不检查
    
    @staticmethod
    def test_initialize_given_no_config_when_load_returns_none_then_log_warning_and_return_false():
        """测试无配置路径时的初始化逻辑（不调用 _load_config，仅校验 _find_config_path）"""
        patcher = SGLangPatcher()
        with patch('ms_service_profiler.patcher.sglang.service_patcher.check_profiling_enabled',
                  return_value=True):
            with patch.object(patcher, '_find_config_path', return_value=None):
                with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.warning') as mock_warning:
                    with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.debug') as mock_debug:
                        result = patcher.initialize()
                        assert result is False
                        mock_debug.assert_called_once_with("Initializing SGLang Service Patcher")
                        mock_warning.assert_called_once_with(
                            "No SGLang config path found, skipping patcher initialization"
                        )
    
    @staticmethod
    def test_initialize_given_valid_config_when_all_steps_succeed_then_return_true():
        """测试成功初始化（仅校验路径、创建 watcher/controller，配置推迟到 enable 时加载）"""
        patcher = SGLangPatcher()
        original_meta_path = sys.meta_path.copy()
        try:
            with patch('ms_service_profiler.patcher.sglang.service_patcher.check_profiling_enabled',
                      return_value=True):
                with patch.object(patcher, '_find_config_path', return_value='/fake/config.yaml'):
                    with patch.object(patcher, '_import_handlers'):
                        with patch('ms_service_profiler.patcher.sglang.service_patcher.SymbolWatchFinder') as MockSWF:
                            with patch('ms_service_profiler.patcher.sglang.service_patcher.HookController') as MockHC:
                                mock_watcher = Mock()
                                MockSWF.return_value = mock_watcher
                                mock_controller = Mock()
                                MockHC.return_value = mock_controller
                                with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.debug') as mock_debug:
                                    mock_meta_path = []
                                    with patch('sys.meta_path', mock_meta_path):
                                        result = patcher.initialize()
                                        assert result is True
                                        assert patcher._controller == mock_controller
                                        mock_watcher.load_handlers.assert_not_called()
                                        MockHC.assert_called_once_with(mock_watcher)
                                        debug_str = str(mock_debug.call_args_list)
                                        assert "Initializing SGLang Service Patcher" in debug_str
                                        assert "Symbol watcher installed" in debug_str
                                        assert "SGLang Service Patcher initialized successfully" in debug_str
                                        assert mock_watcher in mock_meta_path
        finally:
            sys.meta_path = original_meta_path
    
    @staticmethod
    def test_initialize_given_exception_when_any_step_fails_then_log_exception_and_return_false():
        """测试初始化过程中出现异常的处理逻辑"""
        patcher = SGLangPatcher()
        with patch('ms_service_profiler.patcher.sglang.service_patcher.check_profiling_enabled',
                  return_value=True):
            with patch.object(patcher, '_find_config_path', side_effect=Exception("Test error")):
                with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.exception') as mock_exception:
                    result = patcher.initialize()
                    assert result is False
                    mock_exception.assert_called_once()


class TestProperties:
    """测试属性访问"""
    
    @staticmethod
    def test_initialized_property_given_not_initialized_when_accessed_then_return_false():
        """测试未初始化时的initialized属性"""
        # 测试：给定未初始化，当访问属性时，返回False
        patcher = SGLangPatcher()
        # 注意：原代码中 _initialized 初始化为 False
        assert patcher.initialized is False
    
    @staticmethod
    def test_hooks_enabled_property_given_no_controller_when_accessed_then_return_false():
        """测试无控制器时的hooks_enabled属性"""
        # 测试：给定无控制器，当访问属性时，返回False
        patcher = SGLangPatcher()
        assert patcher.hooks_enabled is False
    
    @staticmethod
    def test_hooks_enabled_property_given_controller_disabled_when_accessed_then_return_false():
        """测试控制器禁用时的hooks_enabled属性"""
        # 测试：给定控制器禁用，当访问属性时，返回False
        patcher = SGLangPatcher()
        patcher._controller = Mock()
        patcher._controller.enabled = False
        assert patcher.hooks_enabled is False
    
    @staticmethod
    def test_hooks_enabled_property_given_controller_enabled_when_accessed_then_return_true():
        """测试控制器启用时的hooks_enabled属性"""
        # 测试：给定控制器启用，当访问属性时，返回True
        patcher = SGLangPatcher()
        patcher._controller = Mock()
        patcher._controller.enabled = True
        assert patcher.hooks_enabled is True


class TestHookLifecycle:
    """测试Hook生命周期管理"""
    
    @staticmethod
    def test_enable_hooks_given_no_controller_when_called_then_log_warning():
        """测试无控制器时启用hooks的警告逻辑"""
        # 测试：给定无控制器，当调用启用时，记录警告
        patcher = SGLangPatcher()
        
        with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.warning') as mock_warning:
            patcher.enable_hooks()
            
            mock_warning.assert_called_once_with(
                "Patcher not initialized, cannot enable hooks"
            )
    
    @staticmethod
    def test_enable_hooks_given_controller_exists_when_called_then_delegate_to_controller():
        """测试存在控制器时启用 hooks：先 _load_config 得到 profiling，再 enable(profiling_handlers=..., metrics_handlers=None)"""
        patcher = SGLangPatcher()
        mock_controller = Mock()
        patcher._controller = mock_controller
        mock_handlers = {"sym:func": [MagicMock()]}
        with patch.object(patcher, "_load_config", return_value=mock_handlers):
            patcher.enable_hooks()
        mock_controller.enable.assert_called_once_with(profiling_handlers=mock_handlers, metrics_handlers=None)
    
    @staticmethod
    def test_disable_hooks_given_no_controller_when_called_then_log_warning():
        """测试无控制器时禁用hooks的警告逻辑"""
        # 测试：给定无控制器，当调用禁用时，记录警告
        patcher = SGLangPatcher()
        
        with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.warning') as mock_warning:
            patcher.disable_hooks()
            
            mock_warning.assert_called_once_with(
                "Patcher not initialized, cannot disable hooks"
            )
    
    @staticmethod
    def test_disable_hooks_given_controller_exists_when_called_then_delegate_to_controller():
        """测试存在控制器时禁用hooks的委托逻辑"""
        # 测试：给定存在控制器，当调用禁用时，委托给控制器
        patcher = SGLangPatcher()
        mock_controller = Mock()
        patcher._controller = mock_controller
        
        patcher.disable_hooks()
        
        mock_controller.disable.assert_called_once()
    
    @staticmethod
    def test_get_callbacks_given_no_controller_when_called_then_return_noop_callbacks():
        """测试无控制器时获取回调函数的逻辑"""
        # 测试：给定无控制器，当获取回调函数时，返回空操作回调
        patcher = SGLangPatcher()
        
        with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.warning') as mock_warning:
            start_cb, stop_cb = patcher.get_callbacks()
            
            # 验证回调函数行为
            start_cb()
            stop_cb()
            
            assert mock_warning.call_count == 2  # 每个回调调用一次警告
            mock_warning.assert_has_calls([
                call("Patcher not initialized, callback ignored"),
                call("Patcher not initialized, callback ignored")
            ])
    
    @staticmethod
    def test_get_callbacks_given_controller_exists_when_called_then_return_controller_callbacks():
        """测试存在控制器时获取回调函数的委托逻辑"""
        # 测试：给定存在控制器，当获取回调函数时，返回控制器回调
        patcher = SGLangPatcher()
        mock_controller = Mock()
        mock_start_cb = Mock()
        mock_stop_cb = Mock()
        mock_controller.get_callbacks.return_value = (mock_start_cb, mock_stop_cb)
        patcher._controller = mock_controller
        
        start_cb, stop_cb = patcher.get_callbacks()
        
        assert start_cb == mock_start_cb
        assert stop_cb == mock_stop_cb
        mock_controller.get_callbacks.assert_called_once_with(patcher._load_config)


class TestIntegration:
    """测试集成场景"""
    
    @staticmethod
    def test_full_workflow_given_valid_environment_when_initialized_then_all_components_work():
        """测试完整工作流程"""
        # 测试：给定有效环境，当初始化时，所有组件正常工作
        patcher = SGLangPatcher()
        mock_handlers = {'test.module:function': [MagicMock()]}  # ConfigLoader 返回的 Handler 格式

        # 保存原始meta_path
        original_meta_path = sys.meta_path.copy()

        try:
            # 模拟环境
            with patch('ms_service_profiler.patcher.sglang.service_patcher.check_profiling_enabled',
                      return_value=True):
                with patch.object(patcher, '_load_config', return_value=mock_handlers):
                    with patch.object(patcher, '_import_handlers'):
                        with patch('ms_service_profiler.patcher.sglang.service_patcher.SymbolWatchFinder') as MockSWF:
                            with patch('ms_service_profiler.patcher.sglang.service_patcher.HookController') as MockHC:
                                # 创建模拟对象
                                mock_watcher = Mock()
                                mock_watcher.load_handlers = Mock()
                                mock_watcher.check_and_apply_existing_modules = Mock()
                                MockSWF.return_value = mock_watcher
                                
                                mock_controller = Mock()
                                mock_controller.enabled = False
                                mock_controller.enable = Mock()
                                mock_controller.disable = Mock()
                                mock_controller.get_callbacks = Mock(return_value=(Mock(), Mock()))
                                MockHC.return_value = mock_controller
                                
                                # 1. 初始化
                                with patch('sys.meta_path', []):
                                    result = patcher.initialize()
                                    assert result is True
                                
                                # 2. 验证属性
                                assert patcher.hooks_enabled is False
                                
                                # 3. 启用hooks
                                patcher.enable_hooks()
                                mock_controller.enable.assert_called_once_with(profiling_handlers=mock_handlers, metrics_handlers=None)
                                
                                # 4. 禁用hooks
                                patcher.disable_hooks()
                                mock_controller.disable.assert_called_once()
                                
                                # 5. 获取回调
                                patcher.get_callbacks()
                                mock_controller.get_callbacks.assert_called_once_with(patcher._load_config)
        finally:
            # 恢复原始meta_path
            sys.meta_path = original_meta_path


class TestEdgeCases:
    """测试边界条件"""
    
    @staticmethod
    def test_load_config_given_empty_config_when_loaded_then_return_empty_dict():
        """测试加载空配置文件（ConfigLoader 返回空字典）"""
        # 测试：给定空配置，当加载时，返回空字典
        with patch.object(SGLangPatcher, '_find_config_path', return_value='/mock/path.yaml'):
            with patch('ms_service_profiler.patcher.sglang.service_patcher.ConfigLoader') as MockConfigLoader:
                mock_loader_instance = MagicMock()
                mock_loader_instance.load_profiling.return_value = {}
                MockConfigLoader.return_value = mock_loader_instance
                patcher = SGLangPatcher()
                result = patcher._load_config()
                assert result == {}
    
    @staticmethod
    def test_initialize_given_empty_config_list_when_loaded_then_continue_initialization():
        """测试无配置路径时初始化失败"""
        patcher = SGLangPatcher()
        with patch('ms_service_profiler.patcher.sglang.service_patcher.check_profiling_enabled',
                  return_value=True):
            with patch.object(patcher, '_find_config_path', return_value=None):
                with patch('ms_service_profiler.patcher.sglang.service_patcher.logger.warning') as mock_warning:
                    result = patcher.initialize()
                    assert result is False
                    mock_warning.assert_called_once_with(
                        "No SGLang config path found, skipping patcher initialization"
                    )
    
    @staticmethod
    def test_find_config_path_given_env_var_with_spaces_when_path_valid_then_return_path():
        """测试环境变量路径包含空格的情况"""
        # 测试：给定环境变量路径包含空格，当路径有效时，返回路径
        test_path = "/path with spaces/config.yaml"
        
        def isfile_side_effect(path):
            if path == test_path:
                return True
            # 本地配置文件不存在
            if 'service_profiling_symbols.yaml' in path:
                return False
            return False
        
        with patch.dict(os.environ, {'PROFILING_SYMBOLS_PATH': test_path}):
            with patch('os.path.isfile', side_effect=isfile_side_effect):
                result = SGLangPatcher._find_config_path()
                assert result == test_path
