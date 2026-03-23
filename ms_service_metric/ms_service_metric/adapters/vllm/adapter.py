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
VLLM Metric Adapter - vLLM框架适配器

提供对vLLM推理框架的适配支持，包括：
- 加载V1版本的handlers
- 初始化SymbolHandlerManager
- 与vLLM的插件系统集成

使用示例:
    >>> from ms_service_metric.adapters.vllm import initialize_vllm_metric
    >>> initialize_vllm_metric()
"""

import os
from typing import Optional, Tuple

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.meta_state import set_dp_rank
from ms_service_metric.core.symbol_handler_manager import SymbolHandlerManager

logger = get_logger(__name__)

class VLLMMetricAdapter:
    """vLLM Metric适配器
    
    负责：
    1. 设置dp_rank到meta_state
    2. 加载V1版本的配置和handlers
    3. 初始化SymbolHandlerManager
    4. 提供与vLLM生命周期的集成点
    
    Attributes:
        _manager: SymbolHandlerManager实例
        _initialized: 是否已初始化
    """
    
    def __init__(self):
        """初始化适配器"""
        self._manager: Optional[SymbolHandlerManager] = None
        self._initialized = False
        
    def initialize(self):
        """初始化适配器

        设置vLLM metrics环境，设置dp_rank，加载配置，初始化管理器。
        """
        if self._initialized:
            logger.debug("VLLMMetricAdapter already initialized")
            return

        logger.info("Initializing VLLMMetricAdapter")

        # 设置vLLM metrics环境（多进程、registry、前缀等）
        from ms_service_metric.adapters.vllm.metrics_init import setup_vllm_metrics
        setup_vllm_metrics()

        # 设置meta_state的dp_rank
        self._setup_dp_rank()

        # 创建并初始化SymbolHandlerManager
        self._manager = SymbolHandlerManager()

        # 加载vLLM V1版本的配置
        config_path, default_config_path = self._get_config_path()
        self._manager.initialize(config_path, default_config_path)

        self._initialized = True
        logger.info("VLLMMetricAdapter initialized successfully")
    
    def shutdown(self):
        """关闭适配器"""
        if not self._initialized:
            return
        
        logger.info("Shutting down VLLMMetricAdapter")
        
        if self._manager:
            self._manager.shutdown()
            self._manager = None
        
        self._initialized = False
        logger.info("VLLMMetricAdapter shutdown complete")
    
    def _setup_dp_rank(self):
        """设置dp_rank到meta_state
        
        尝试从vLLM的各种配置中获取dp_rank。
        """
        dp_rank = -1
        
        # 尝试从环境变量获取
        env_dp_rank = os.getenv("VLLM_DP_RANK")
        if env_dp_rank:
            try:
                dp_rank = int(env_dp_rank)
                logger.debug(f"Got dp_rank from environment: {dp_rank}")
            except ValueError:
                pass
        
        # 尝试从vLLM内部获取
        if dp_rank < 0:
            try:
                from vllm.distributed.parallel_state import get_data_parallel_rank
                dp_rank = get_data_parallel_rank()
                logger.debug(f"Got dp_rank from vLLM: {dp_rank}")
            except Exception:
                pass
        
        # 设置到meta_state
        set_dp_rank(dp_rank)
        logger.debug(f"Set dp_rank to meta_state: {dp_rank}")
    
    def _get_config_path(self) -> Tuple[Optional[str], Optional[str]]:
        """获取配置文件路径
        
        优先使用环境变量指定的配置，否则使用默认V1配置。
        
        Returns:
            配置文件路径，如果没有合适的配置则返回None
        """
        # 获取适配器目录
        adapter_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(adapter_dir, "config")
        default_config_path = os.path.join(config_dir, "default.yaml")
        
        # 首先检查环境变量指定的配置
        env_config = os.getenv("MS_SERVICE_METRIC_VLLM_CONFIG")
        if env_config and os.path.exists(env_config):
            logger.debug(f"Using config from environment: {env_config}")
            return env_config, default_config_path
        
        # 使用V1配置
        config_path = os.path.join(config_dir, "v1_metrics.yaml")
        if os.path.exists(config_path):
            logger.debug(f"Using V1 config: {config_path}")
            return config_path, default_config_path
        
        logger.warning("No config file found for vLLM adapter")
        return None, default_config_path
    
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
_vllm_adapter_instance: Optional[VLLMMetricAdapter] = None


def get_vllm_adapter() -> VLLMMetricAdapter:
    """获取全局VLLM适配器实例（单例模式）
    
    Returns:
        VLLMMetricAdapter单例实例
    """
    global _vllm_adapter_instance
    if _vllm_adapter_instance is None:
        _vllm_adapter_instance = VLLMMetricAdapter()
    return _vllm_adapter_instance


def initialize_vllm_metric():
    """初始化vLLM metric收集
    
    这是主要的初始化入口，应在vLLM启动时调用。
    
    Example:
        >>> from ms_service_metric.adapters.vllm import initialize_vllm_metric
        >>> initialize_vllm_metric()
    """
    adapter = get_vllm_adapter()
    adapter.initialize()
