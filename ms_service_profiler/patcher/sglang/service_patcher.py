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

from ..core.utils import check_profiling_enabled
from ..core.config_loader import ConfigLoader
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
    def _find_config_path() -> Optional[str]:
        """查找性能分析配置文件，按优先级顺序查找。
        
        查找顺序：
        1. PROFILING_SYMBOLS_PATH 环境变量配置路径
        2. 本项目目录: <this>/sglang/config/service_profiling_symbols.yaml

        Returns:
            Optional[str]: 配置文件路径，如果未找到则返回 None
        """
        path = None
        env_path = os.environ.get('PROFILING_SYMBOLS_PATH')
        if env_path and str(env_path).lower().endswith(('.yaml', '.yml')):
            if os.path.isfile(env_path):
                logger.debug("Loading profiling symbols from env path: %s", env_path)
                path = env_path
        elif env_path and not str(env_path).lower().endswith(('.yaml', '.yml')):
            logger.warning("PROFILING_SYMBOLS_PATH is not a yaml file: %s", env_path)

        if path is None:
            local_path = os.path.join(os.path.dirname(__file__), 'config', 'service_profiling_symbols.yaml')
            if os.path.isfile(local_path):
                logger.debug("Using SGLang profiling symbols from local project: %s", local_path)
                path = local_path
        if path:
            logger.info("Using profiling config path: %s", path)
        return path

    def _load_config(self):
        """加载配置文件（通过 ConfigLoader）。

        Returns:
            Optional[Dict[str, List[DynamicHooker]]]: 由 ConfigLoader 解析得到的 Handler 列表，
                失败时返回 None
        """
        config_path = self._find_config_path()
        if not config_path:
            logger.warning("No SGLang profiling config found.")
            return None
        logger.info("Loading SGLang profiling symbols from: %s", config_path)
        loader = ConfigLoader(config_path)
        return loader.load()
    
    def _import_handlers(self):
        """导入内置 handlers。
        """
        from .handlers import scheduler_handlers, request_handlers, model_handlers
        logger.debug("Initializing service patcher with SGLang interface")

    def initialize(self) -> bool:
        """初始化服务分析器。
        
        执行完整的初始化流程：
        1. 检查环境变量
        2. 加载配置文件（ConfigLoader）
        3. 导入内置 handlers
        4. 创建 SymbolWatchFinder 和 HookController
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            if not check_profiling_enabled():
                return False
            logger.debug("Initializing SGLang Service Patcher")
            # 仅校验配置路径存在，不在此处加载配置（ConfigLoader.load / _resolve_handler_func
            # 推迟到 HookController.enable 时执行，即 _enabled 为 True 时再加载）
            if self._find_config_path() is None:
                logger.warning("No SGLang config path found, skipping patcher initialization")
                return False
            self._import_handlers()
            # 创建 SymbolWatchFinder（未加载配置）并安装；首次 enable() 时再加载配置并 load_handlers
            watcher = SymbolWatchFinder()
            sys.meta_path.insert(0, watcher)
            logger.debug("Symbol watcher installed")
            self._controller = HookController(watcher)
            self._initialized = True
            logger.debug("SGLang Service Patcher initialized successfully")
            return True
        except Exception as e:
            logger.exception("Failed to initialize SGLang Service Patcher: %s", str(e))
            self._initialized = False
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
        """启用所有 hooks（先加载配置得到 Handler 列表，再交给 controller.enable）。"""
        if self._controller is None:
            logger.warning("Patcher not initialized, cannot enable hooks")
            return
        handlers = self._load_config()
        self._controller.enable(handlers)

    def disable_hooks(self) -> None:
        """禁用所有 hooks。"""
        if self._controller is None:
            logger.warning("Patcher not initialized, cannot disable hooks")
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
                logger.warning("Patcher not initialized, callback ignored")
            return noop, noop
        return self._controller.get_callbacks(self._load_config)
