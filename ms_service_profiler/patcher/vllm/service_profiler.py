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

"""
vLLM 框架适配器。

职责：
- 框架特定的配置加载
- 版本检测
- 初始化 SymbolWatchFinder + HookController
- 对外暴露 enable_hooks/disable_hooks

依赖：
- HookController（控制层）
- SymbolWatchFinder（执行层）
"""

import os
import sys
import importlib_metadata
from typing import Optional, Tuple, Callable

from ..core.utils import load_yaml_config, parse_version_tuple, check_profiling_enabled
from ..core.symbol_watcher import SymbolWatchFinder
from ..core.hook_controller import HookController
from ..core.logger import logger


class VLLMProfiler:
    """vLLM 框架适配器。
    
    该类只负责 vLLM 特定的逻辑：
    - 配置文件路径查找
    - vLLM 版本检测
    - handlers 导入
    
    hook 的启用/禁用由 HookController 统一管理。
    """
    
    def __init__(self):
        """初始化 vLLM Profiler。"""
        self._vllm_use_v1 = VLLMProfiler._detect_version()
        self._controller: Optional[HookController] = None
        self._initialized = False
    
    # -------------------------------------------------------------------------
    # 版本检测
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _auto_detect_v1_default() -> str:
        """根据已安装的 vLLM 版本自动决定默认 V1 使用情况。"""
        try:
            vllm_version = importlib_metadata.version("vllm")
            major, minor, patch = parse_version_tuple(vllm_version)
            use_v1 = (major, minor, patch) >= (0, 9, 2)
            logger.info(
                f"VLLM_USE_V1 not set, auto-detected via vLLM {vllm_version}: default {'1' if use_v1 else '0'}"
            )
            return "1" if use_v1 else "0"
        except Exception:
            logger.info("VLLM_USE_V1 not set and vLLM version unknown; default to 0 (V0)")
            return "0"

    @staticmethod
    def _detect_version() -> str:
        """检测 vLLM 版本。"""
        env_v1 = os.environ.get('VLLM_USE_V1')
        return env_v1 if env_v1 is not None else VLLMProfiler._auto_detect_v1_default()
    
    # -------------------------------------------------------------------------
    # 配置加载
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _find_config_path() -> Optional[str]:
        """查找性能分析配置文件，按优先级顺序查找。"""
        # 1) local project config path
        try:
            local_candidate = os.path.join(
                os.path.dirname(__file__), 'config', 'service_profiling_symbols.yaml'
            )
            if os.path.isfile(local_candidate):
                logger.debug(f"Loading profiling symbols from local config file: {local_candidate}")
                return local_candidate
        except Exception as e:
            logger.warning(f"Failed to find profiling symbols from local project: {e}")
        
        # 2) user config path
        try:
            try:
                import vllm  # type: ignore
                vllm_version = getattr(vllm, '__version__', None)
            except Exception as e:
                logger.debug(f"vllm not available for version detection: {e}")
                vllm_version = None
            
            try:
                from vllm_ascend import register_service_profiling  # type: ignore
                register_service_profiling()
            except Exception as e:
                logger.debug(f"Cannot using register_service_profiling to get default symbols config: {e}")

            if vllm_version:
                home_dir = os.path.expanduser('~')
                candidate = os.path.join(
                    home_dir, '.config', 'vllm_ascend',
                    f"service_profiling_symbols.{vllm_version}.yaml",
                )
                if os.path.isfile(candidate):
                    logger.debug(f"Loading profiling symbols from user config: {candidate}")
                    return candidate
        except Exception as e:
            logger.warning(f"Failed to find profiling symbols from default path: {e}")

        return None

    def _load_config(self):
        """加载配置文件。"""
        def _write_profiling_symbols(env_path, default_cfg):
            try:
                parent_dir = os.path.dirname(env_path) or '.'
                os.makedirs(parent_dir, exist_ok=True)
                with open(default_cfg, 'r', encoding='utf-8') as src, \
                        open(env_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
                logger.debug(f"Wrote profiling symbols to env path: {env_path}")
                return load_yaml_config(env_path)
            except Exception as e:
                logger.warning(f"Failed to write profiling symbols to env path {env_path}: {e}")
                return None

        default_cfg = self._find_config_path()
        
        env_path = os.environ.get('PROFILING_SYMBOLS_PATH')
        if env_path and str(env_path).lower().endswith(('.yaml', '.yml')):
            if os.path.isfile(env_path):
                logger.debug(f"Loading profiling symbols from env path: {env_path}")
                return load_yaml_config(env_path)
            if default_cfg:
                result = _write_profiling_symbols(env_path, default_cfg)
                if result is not None:
                    return result
            else:
                logger.warning("No default config file found to populate PROFILING_SYMBOLS_PATH")
        elif env_path and not str(env_path).lower().endswith(('.yaml', '.yml')):
            logger.warning(f"PROFILING_SYMBOLS_PATH is not a yaml file: {env_path}")

        if not default_cfg:
            logger.warning("No config file found")
            return None
        return load_yaml_config(default_cfg)
    
    # -------------------------------------------------------------------------
    # 初始化
    # -------------------------------------------------------------------------
    
    def _import_handlers(self):
        """按版本导入内置 handlers。"""
        if self._vllm_use_v1 == "0":
            logger.debug("Initializing service profiler with vLLM V0 interface")
            from .handlers.v0 import batch_handlers, kvcache_handlers, model_handlers, request_handlers
        elif self._vllm_use_v1 == "1":
            logger.debug("Initializing service profiler with vLLM V1 interface")
            from .handlers.v1 import batch_handlers, kvcache_handlers, meta_handlers, model_handlers, request_handlers
        else:
            logger.error(f"unknown vLLM interface version: VLLM_USE_V1={self._vllm_use_v1}")

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
            if not check_profiling_enabled():
                return False
            logger.debug("Initializing VLLM Service Profiler")
            
            # 1. 加载配置
            config_data = self._load_config()
            if not config_data:
                logger.warning("No VLLM configuration loaded, skipping profiler initialization")
                return False
            
            # 2. 导入 handlers
            self._import_handlers()
            
            # 3. 创建 SymbolWatchFinder 并安装
            watcher = SymbolWatchFinder()
            watcher.load_symbol_config(config_data)
            sys.meta_path.insert(0, watcher)
            logger.debug("Symbol watcher installed")
            
            # 4. 为已加载的模块准备 hooks
            watcher.check_and_apply_existing_modules()
            
            # 5. 创建 HookController
            self._controller = HookController(watcher)
            
            self._initialized = True
            logger.debug("VLLM Service Profiler initialized successfully")
            return True
            
        except Exception as e:
            logger.exception("Failed to initialize VLLM Service Profiler: %s", str(e))
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

    @property
    def vllm_version(self) -> str:
        """获取 vLLM 版本标识。"""
        return self._vllm_use_v1
