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
from typing import Callable, Optional, Tuple

from ..core.utils import load_yaml_config, check_profiling_enabled
from ..core.symbol_watcher import SymbolWatchFinder
from ..core.hook_controller import HookController
from ..core.logger import logger


class SGLangPatcher:
    """SGLang框架专用Patcher"""
    
    def __init__(self):
        """初始化SGLang Patcher"""
        self._controller: Optional[HookController] = None
        self._initialized = False

    @staticmethod
    def _find_config_path():
        """查找性能分析配置文件，按优先级顺序查找。
        
        查找顺序：
        1. PROFILING_SYMBOLS_PATH 环境变量配置路径
        2. 本项目目录: <this>/sglang/config/service_profiling_symbols.yaml

        Returns:
            Optional[str]: 配置文件路径，如果未找到则返回 None
        """
        # 读取环境变量配置路径
        env_path = os.environ.get('PROFILING_SYMBOLS_PATH')
        if env_path and str(env_path).lower().endswith(('.yaml', '.yml')):
            # 环境变量目标文件已存在：直接加载
            if os.path.isfile(env_path):
                logger.debug("Loading profiling symbols from env path: %s", env_path)
                return env_path
        elif env_path and not str(env_path).lower().endswith(('.yaml', '.yml')):
            logger.warning("PROFILING_SYMBOLS_PATH is not a yaml file: %s", env_path)

        # 查找本地目录下的备选路径
        local_path = os.path.join(os.path.dirname(__file__), 'config', 'service_profiling_symbols.yaml')
        if os.path.isfile(local_path):
            logger.debug("Using SGLang profiling symbols from local project: %s", local_path)
            return local_path
        
        return None
        
    @staticmethod
    def _load_config():
        """加载配置文件。
        
        Returns:
            Optional[Dict]: 配置数据，失败时返回 None
        """
        config_path = SGLangPatcher._find_config_path()
        if config_path:
            logger.info("Loading SGLang profiling symbols path: %s", config_path)
            return load_yaml_config(config_path)
        
        logger.warning("No SGLang profiling config found.")
        return None
    
    def _import_handlers(self):
        """导入内置 handlers。
        """
        logger.debug("Initializing service patcher with SGLang interface")

    def initialize(self) -> bool:
        """初始化服务分析器。
        
        执行完整的初始化流程：
        1. 检查环境变量
        2. 加载配置文件
        3. 导入内置 handlers
        4. 创建 SymbolWatchFinder 和 HookController
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 1. 检查环境是否启用
            if not check_profiling_enabled():
                return False
            logger.debug("Initializing SGLang Service Patcher")
            
            # 2. 加载配置
            config_data = self._load_config()
            if not config_data:
                logger.warning("No SGLang configuration loaded, skipping patcher initialization")
                return False
            
            # 3. 按版本导入内置 handlers
            self._import_handlers()
            
            # 4. 创建并初始化symbol监听器
            watcher = SymbolWatchFinder()
            watcher.load_symbol_config(config_data)
            sys.meta_path.insert(0, watcher)
            logger.debug("Symbol watcher installed")

            # 5. 为已加载的模块准备 hooks
            watcher.check_and_apply_existing_modules()
            
            # 6. 创建 HookController
            self._controller = HookController(watcher)

            self._hooks_applied = True
            logger.debug("SGLang Service Patcher initialized successfully")
            return True
        except Exception as e:
            logger.exception("Failed to initialize SGLang Service Patcher: %s", str(e))
            self._hooks_applied = False
            return False
    
    # -------------------------------------------------------------------------
    # Hooks 生命周期（委托给 HookController）
    # -------------------------------------------------------------------------

    @property
    def initialized(self) -> bool:
        """Profiler 是否已初始化。"""
        return self._initialized

    @property
    def hooks_enabled(self) -> bool:
        """hooks 是否已启用。"""
        if self._controller is None:
            return False
        return self._controller.enabled

    def enable_hooks(self) -> None:
        """启用所有 hooks。"""
        if self._controller is None:
            logger.warning("Profiler not initialized, cannot enable hooks")
            return
        self._controller.enable(self._load_config)

    def disable_hooks(self) -> None:
        """禁用所有 hooks。"""
        if self._controller is None:
            logger.warning("Profiler not initialized, cannot disable hooks")
            return
        self._controller.disable()

    # -------------------------------------------------------------------------
    # C++ 回调（委托给 HookController）
    # -------------------------------------------------------------------------

    def get_callbacks(self) -> Tuple[Callable[[], None], Callable[[], None]]:
        """返回可注册到 C++ 的回调函数对（start, stop）。
        
        Returns:
            (on_start_callback, on_stop_callback)
        """
        if self._controller is None:
            # 如果还没初始化，返回空操作的回调
            def noop():
                logger.warning("Profiler not initialized, callback ignored")
            return noop, noop
        return self._controller.get_callbacks(self._load_config)
