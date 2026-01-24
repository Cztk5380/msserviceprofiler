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
import importlib_metadata
from typing import Optional

from ..core.utils import load_yaml_config, parse_version_tuple, check_profiling_enabled
from ..core.symbol_watcher import SymbolWatchFinder
from ..core.logger import logger


class VLLMProfiler:
    """vLLM框架专用Profiler，直接组合使用小模块。"""
    
    def __init__(self):
        """初始化vLLM Profiler。"""
        self._vllm_use_v1 = VLLMProfiler._detect_version()
        self._symbol_watcher = None
        self._hooks_applied = False
    
    @staticmethod
    def _auto_detect_v1_default() -> str:
        """根据已安装的 vLLM 版本自动决定默认 V1 使用情况。
        
        启发式规则：对于较新的 vLLM (>= 0.9.2) 默认使用 V1，否则使用 V0。
        如果无法确定版本，为了安全起见回退到 V0。
        
        Returns:
            str: "1" 表示使用 V1，"0" 表示使用 V0
            
        Note:
            该方法会检查环境变量 VLLM_USE_V1，如果未设置则自动检测。
        """
        try:
            vllm_version = importlib_metadata.version("vllm")
            major, minor, patch = parse_version_tuple(vllm_version)
            use_v1 = (major, minor, patch) >= (0, 9, 2)
            logger.info(
                f"VLLM_USE_V1 not set, auto-detected via vLLM {vllm_version}: default {'1' if use_v1 else '0'}"
            )
            return "1" if use_v1 else "0"
        except Exception as e:
            logger.info("VLLM_USE_V1 not set and vLLM version unknown; default to 0 (V0)")
            return "0"

    @staticmethod
    def _detect_version() -> str:
        """检测 vLLM 版本。
        
        Returns:
            str: vLLM 版本标识
        """
        env_v1 = os.environ.get('VLLM_USE_V1')
        return env_v1 if env_v1 is not None else VLLMProfiler._auto_detect_v1_default()
    
    @staticmethod
    def _find_config_path() -> Optional[str]:
        """查找性能分析配置文件，按优先级顺序查找。
        
        查找顺序：
        1. 本项目目录: <this>/vllm/config/service_profiling_symbols.yaml
        2. 用户配置目录: ~/.config/vllm_ascend/service_profiling_symbols.{VLLM_VERSION}.yaml

        Returns:
            Optional[str]: 配置文件路径，如果未找到则返回 None
        """
        # 1) local project config path
        try:
            local_candidate = os.path.join(os.path.dirname(__file__), 'vllm', 'config', 'service_profiling_symbols.yaml')
            if os.path.isfile(local_candidate):
                logger.debug(f"Loading profiling symbols from local config file: {local_candidate}")
                return local_candidate
        except Exception as e:
            logger.warning(f"Failed to find profiling symbols from local project: {e}")
        
        # 2) user config path: ~/.config/vllm_ascend/service_profiling_symbols.{VLLM_VERSION}.yaml
        try:
            try:
                import vllm  # type: ignore
                vllm_version = getattr(vllm, '__version__', None)
            except Exception as e:
                logger.debug(f"vllm not available for version detection: {e}")
                vllm_version = None
            
            try:
                from vllm_ascend import register_service_profiling # type: ignore
                register_service_profiling()
            except Exception as e:
                logger.debug(f"Cannot using register_service_profiling to get default symbols config: {e}")

            if vllm_version:
                home_dir = os.path.expanduser('~')
                candidate = os.path.join(
                    home_dir,
                    '.config',
                    'vllm_ascend',
                    f"service_profiling_symbols.{vllm_version}.yaml",
                )
                if os.path.isfile(candidate):
                    logger.debug(f"Loading profiling symbols from user config: {candidate}")
                    return candidate
        except Exception as e:
            logger.warning(f"Failed to find profiling symbols from default path: {e}")

        return None

    def _load_config(self):
        """加载配置文件。
        
        Returns:
            Optional[Dict]: 配置数据，失败时返回 None
        """
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
            # 环境变量目标文件已存在：直接加载
            if os.path.isfile(env_path):
                logger.debug(f"Loading profiling symbols from env path: {env_path}")
                return load_yaml_config(env_path)

        # 目标文件不存在：若有默认配置，尝试复制填充
            if default_cfg:
                result = _write_profiling_symbols(env_path, default_cfg)
                if result is not None:
                    return result
            else:
                logger.warning("No default config file found to populate PROFILING_SYMBOLS_PATH")
        elif env_path and not str(env_path).lower().endswith(('.yaml', '.yml')):
            logger.warning(f"PROFILING_SYMBOLS_PATH is not a yaml file: {env_path}")

        # 回退：按默认查找顺序加载
        if not default_cfg:
            logger.warning("No config file found")
            return None
        return load_yaml_config(default_cfg)
    
    def _import_handlers(self):
        """按版本导入内置 handlers。
        
        根据 vLLM 版本导入相应的内置 hooker 模块。
        """
        if self._vllm_use_v1 == "0":
            logger.debug("Initializing service profiler with vLLM V0 interface")
            from .handlers.v0 import batch_handlers, kvcache_handlers, model_handlers, request_handlers
        elif self._vllm_use_v1 == "1":
            logger.debug("Initializing service profiler with vLLM V1 interface")
            from .handlers.v1 import batch_handlers, kvcache_handlers, meta_handlers, model_handlers, request_handlers
        else:
            logger.error(f"unknown vLLM interface version: VLLM_USE_V1={self._vllm_use_v1}")
            return
    
    def _init_symbol_watcher(self, config_data):
        """初始化 symbol 监听器。
        
        Args:
            config_data: 配置数据
        """
        self._symbol_watcher = SymbolWatchFinder()
        self._symbol_watcher.load_symbol_config(config_data)
        
        # 安装到 sys.meta_path
        sys.meta_path.insert(0, self._symbol_watcher)
        logger.debug("Symbol watcher installed")
        
        # 检查目标模块是否已经被导入，如果是则立即应用 hooks
        self._symbol_watcher.check_and_apply_existing_modules()

    def initialize(self) -> bool:
        """初始化服务分析器。
        
        执行完整的初始化流程：
        1. 检查环境变量
        2. 加载配置文件
        3. 导入内置 handlers
        4. 初始化 symbol 监听器
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 1. 检查环境是否启用
            if not check_profiling_enabled():
                return False
            logger.debug("Initializing VLLM Service Profiler")
            
            # 2. 加载vLLM特定配置
            config_data = self._load_config()
            if not config_data:
                logger.warning("No VLLM configuration loaded, skipping profiler initialization")
                return False
            
            # 3. 按版本导入内置 handlers
            self._import_handlers()
            
            # 4. 创建并初始化symbol监听器
            self._init_symbol_watcher(config_data)

            self._hooks_applied = True
            logger.debug("VLLM Service Profiler initialized successfully")
            return True
        except Exception as e:
            logger.exception("Failed to initialize VLLM Service Profiler: %s", str(e))
        self._hooks_applied = False
    
    @property
    def vllm_version(self) -> str:
        """获取vLLM版本标识。
        
        Returns:
            str: vLLM版本标识
        """
        return self._vllm_use_v1
    
    @property
    def hooks_applied(self) -> bool:
        """获取hooks是否已应用的状态。
        
        Returns:
            bool: hooks是否已应用
        """
        return self._hooks_applied