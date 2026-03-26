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
SGLang Metric Adapter - SGLang框架适配器

提供对SGLang推理框架的适配支持。

使用示例:
    >>> from ms_service_metric.adapters.sglang import initialize_sglang_metric
    >>> initialize_sglang_metric()
"""

import os
from typing import Optional

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.utils.version import get_package_version
from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager


logger = get_logger(__name__)

class SGLangMetricAdapter:
    """SGLang Metric适配器
    
    负责：
    1. 检测SGLang版本
    2. 加载对应版本的配置和handlers
    3. 初始化SymbolHandlerManager
    
    Attributes:
        _manager: SymbolHandlerManager实例
        _version: 检测到的SGLang版本
        _initialized: 是否已初始化
    """
    
    def __init__(self):
        """初始化适配器"""
        self._manager: Optional[SymbolHandlerManager] = None
        self._version: Optional[str] = None
        self._initialized: bool = False
        
    def initialize(self):
        """初始化适配器
        
        检测SGLang版本，加载配置，初始化管理器。
        """
        if self._initialized:
            logger.debug("SGLangMetricAdapter already initialized")
            return
        
        logger.info("Initializing SGLangMetricAdapter")
        
        # 检测SGLang版本
        self._version = self._detect_sglang_version()
        logger.info(f"Detected SGLang version: {self._version}")
        
        # 创建并初始化SymbolHandlerManager
        self._manager = SymbolHandlerManager()
        
        # 加载SGLang特定的配置
        config_path = self._get_config_path()
        self._manager.initialize(config_path)
        
        self._initialized = True
        logger.info("SGLangMetricAdapter initialized successfully")
    
    def shutdown(self):
        """关闭适配器"""
        if not self._initialized:
            return
        
        logger.info("Shutting down SGLangMetricAdapter")
        
        if self._manager:
            self._manager.shutdown()
            self._manager = None
        
        self._initialized = False
        logger.info("SGLangMetricAdapter shutdown complete")
    
    def _detect_sglang_version(self) -> Optional[str]:
        """检测SGLang版本
        
        使用 get_package_version 获取 sglang 包版本信息。
        
        Returns:
            版本字符串，如果未安装则返回None
        """
        version = get_package_version("sglang")
        if version:
            logger.debug(f"SGLang version: {version}")
            return version
        logger.warning("SGLang not installed")
        return None
    
    def _get_config_path(self) -> Optional[str]:
        """获取配置文件路径
        
        Returns:
            配置文件路径，如果没有合适的配置则返回None
        """
        
        # 获取适配器目录
        adapter_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(adapter_dir, "config")
        
        # 首先检查环境变量指定的配置
        env_config = os.getenv("MS_SERVICE_METRIC_SGLANG_CONFIG")
        if env_config and os.path.exists(env_config):
            logger.debug(f"Using config from environment: {env_config}")
            return env_config
        
        # 使用默认配置
        default_config = os.path.join(config_dir, "default.yaml")
        if os.path.exists(default_config):
            logger.debug(f"Using default config: {default_config}")
            return default_config
        
        logger.warning("No config file found for SGLang adapter")
        return None
    
    def get_manager(self) -> Optional[SymbolHandlerManager]:
        """获取SymbolHandlerManager实例
        
        Returns:
            SymbolHandlerManager实例或None
        """
        return self._manager
    
    def is_initialized(self) -> bool:
        """检查是否已初始化
        
        Returns:
            是否已初始化
        """
        return self._initialized


# 全局适配器实例
_sglang_adapter_instance: Optional[SGLangMetricAdapter] = None


def get_sglang_adapter() -> SGLangMetricAdapter:
    """获取全局SGLang适配器实例（单例模式）
    
    Returns:
        SGLangMetricAdapter单例实例
    """
    global _sglang_adapter_instance
    if _sglang_adapter_instance is None:
        _sglang_adapter_instance = SGLangMetricAdapter()
    return _sglang_adapter_instance


def initialize_sglang_metric():
    """初始化SGLang metric收集
    
    这是主要的初始化入口，应在SGLang启动时调用。
    
    Example:
        >>> from ms_service_metric.adapters.sglang import initialize_sglang_metric
        >>> initialize_sglang_metric()
    """
    adapter = get_sglang_adapter()
    adapter.initialize()
