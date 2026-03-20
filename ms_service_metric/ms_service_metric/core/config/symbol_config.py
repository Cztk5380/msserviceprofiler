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
SymbolConfig: 配置管理类

职责：
- 读取YAML配置文件
- 读取用户配置、默认配置
- 配置合并、自动赋默认值
- 所有配置相关的功能

配置格式示例（数组格式，与原始配置兼容）：
    - symbol: module.path:ClassName.method_name
      handler: module.path:function_name
      min_version: "0.1.0"
      max_version: "1.0.0"
      need_locals: false
      metrics:
        - name: metric_name
          type: timer
          expr: "duration"
          buckets: [0.1, 0.5, 1.0]

    - symbol: module.path:ClassName.method_name
      metrics:
        - name: metric_name
          type: timer
          labels:
            - name: label_name
              expr: "expression"
"""

import copy
import os
from typing import Any, Dict, List, Optional

import yaml

from ms_service_metric.utils.exceptions import ConfigError
from ms_service_metric.utils.logger import get_logger

logger = get_logger("symbol_config")


class SymbolConfig:
    """Symbol配置管理类
    
    负责加载和合并用户配置与默认配置，提供统一的配置访问接口。
    """
    
    # 环境变量名称
    ENV_CONFIG_PATH = "MS_SERVICE_METRIC_CONFIG_PATH"
    
    def __init__(self, 
                 user_config_path: Optional[str] = None,
                 default_config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            user_config_path: 用户配置文件路径
            default_config_path: 默认配置文件路径
        """
        self._user_config_path = user_config_path
        self._default_config_path = default_config_path or os.path.join(os.path.dirname(__file__), "config.yaml")
        self._config: Dict[str, List[dict]] = {}
        
        logger.debug(f"SymbolConfig initialized: user={user_config_path}, default={default_config_path}")
        
    def load(self, config_path: Optional[str] = None, default_config_path: Optional[str] = None) -> Dict[str, List[dict]]:
        """
        加载并合并配置
        
        加载顺序：
        1. 加载默认配置
        2. 加载用户配置（优先使用传入的config_path，其次使用构造函数传入的路径）
        3. 合并配置（用户配置覆盖默认配置）
        4. 填充默认值
        
        Args:
            config_path: 可选的配置文件路径，如果提供则作为用户配置加载
            
        Returns:
            合并后的配置字典，key为symbol_path，value为handler配置列表
        """
        logger.info("Loading configuration...")
        
        # 如果提供了config_path，临时设置为用户配置路径
        if default_config_path:
            self._default_config_path = default_config_path
        if config_path:
            self._user_config_path = config_path
        
        # 打印加载的文件路径（方便排查）
        logger.info(f"Default config path: {self._default_config_path}")
        logger.info(f"User config path: {self._user_config_path or 'Not set'}")
        
        # 1. 加载默认配置
        default_config = self._load_default_config()
        logger.debug(f"Default config loaded: {len(default_config)} symbols")
        
        # 2. 加载用户配置
        user_config = self._load_user_config()
        logger.debug(f"User config loaded: {len(user_config)} symbols")
        
        # 3. 合并配置（用户配置覆盖默认配置）
        self._config = self._merge_configs(default_config, user_config)
        logger.debug(f"Configs merged: {len(self._config)} symbols")
        
        # 4. 填充默认值
        self._fill_defaults()
        
        logger.info(f"Configuration loaded successfully: {len(self._config)} symbols")
        return self._config
        
    def reload(self) -> Dict[str, List[dict]]:
        """
        重新加载配置
        
        清除当前配置并重新加载。
        
        Returns:
            重新加载后的配置字典
        """
        logger.info("Reloading configuration...")
        self._config.clear()
        return self.load()
        
    def _load_default_config(self) -> dict:
        """
        加载默认配置
        
        从默认配置文件路径加载配置。
        
        Returns:
            默认配置字典
        """
        if self._default_config_path and os.path.exists(self._default_config_path):
            logger.debug(f"Loading default config from: {self._default_config_path}")
            return self._load_yaml(self._default_config_path)
        logger.debug("No default config file found")
        return {}
        
    def _load_user_config(self) -> dict:
        """
        加载用户配置
        
        加载优先级：
        1. 环境变量 MS_SERVICE_METRIC_CONFIG_PATH
        2. 构造函数传入的 user_config_path
        
        Returns:
            用户配置字典
        """
        # 优先从环境变量读取
        env_path = os.environ.get(self.ENV_CONFIG_PATH)
        if env_path and os.path.exists(env_path):
            logger.debug(f"Loading user config from environment: {env_path}")
            return self._load_yaml(env_path)
            
        if self._user_config_path and os.path.exists(self._user_config_path):
            logger.debug(f"Loading user config from: {self._user_config_path}")
            return self._load_yaml(self._user_config_path)
            
        logger.debug("No user config file found")
        return {}
        
    def _load_yaml(self, path: str) -> dict:
        """
        加载YAML文件
        
        支持两种格式：
        1. 数组格式（原始格式）: [{symbol: ..., handler: ...}, ...]
        2. 字典格式: {symbol_path: [handlers...], ...}
        
        统一转换为字典格式返回。
        
        Args:
            path: YAML文件路径
            
        Returns:
            解析后的字典，格式为 {symbol_path: [handler_configs...]}
            
        Raises:
            ConfigError: 文件读取或解析失败
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
                
            if not content:
                return {}
            
            # 如果是列表格式（原始配置格式），转换为字典格式
            if isinstance(content, list):
                return self._convert_array_config(content)
            
            # 如果是字典格式，直接返回
            if isinstance(content, dict):
                return content

            logger.warning(f"Unexpected config format in {path}: {type(content)}")
            return {}
            
        except FileNotFoundError:
            logger.error(f"Config file not found: {path}")
            raise ConfigError(f"Config file not found: {path}")
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML file {path}: {e}")
            raise ConfigError(f"Failed to parse YAML file {path}: {e}")
        except Exception as e:
            logger.error(f"Failed to load config file {path}: {e}")
            raise ConfigError(f"Failed to load config file {path}: {e}")
    
    def _convert_array_config(self, config_list: list) -> dict:
        """
        将数组格式的配置转换为字典格式
        
        原始格式: [{symbol: ..., handler: ..., metrics: ...}, ...]
        目标格式: {symbol_path: [{handler: ..., metrics: ...}], ...}
        
        与原项目配置格式保持一致：
        - 有handler字段：使用指定的handler
        - 无handler字段但有metrics字段：使用默认handler（在Handler.from_config中处理）
        
        Args:
            config_list: 数组格式的配置列表
            
        Returns:
            字典格式的配置
        """
        result = {}
        
        for item in config_list:
            if not isinstance(item, dict):
                logger.warning(f"Invalid config item: {item}")
                continue
            
            # 获取symbol路径
            symbol_path = item.get('symbol')
            if not symbol_path:
                logger.warning(f"Config item missing 'symbol' field: {item}")
                continue
            
            # 构建handler配置（排除symbol字段）
            handler_config = {k: v for k, v in item.items() if k != 'symbol'}
            
            # 注意：不自动添加handler字段
            # 如果没有handler但有metrics，Handler.from_config会使用默认handler
            
            # 添加到结果
            if symbol_path not in result:
                result[symbol_path] = []
            result[symbol_path].append(handler_config)
            
            logger.debug(f"Converted config for symbol: {symbol_path}")
        
        return result
            
    def _merge_configs(self, default: dict, user: dict) -> dict:
        """
        合并配置
        
        合并策略：
        - 对于同一个symbol，用户配置的handlers追加到默认配置后面
        - 对于新的symbol，直接添加
        
        Args:
            default: 默认配置
            user: 用户配置
            
        Returns:
            合并后的配置
        """
        # 深拷贝默认配置
        merged = copy.deepcopy(default)
        
        for symbol_path, handlers in user.items():
            if symbol_path in merged:
                # 合并handlers列表（用户配置追加到后面）
                if isinstance(handlers, list):
                    merged[symbol_path].extend(handlers)
                else:
                    merged[symbol_path].append(handlers)
                logger.debug(f"Merged handlers for symbol: {symbol_path}")
            else:
                # 新的symbol
                merged[symbol_path] = handlers if isinstance(handlers, list) else [handlers]
                logger.debug(f"Added new symbol: {symbol_path}")
                
        return merged
        
    def _fill_defaults(self):
        """
        为配置填充默认值
        
        为每个handler填充默认配置项。
        """
        for symbol_path, handlers in self._config.items():
            if not isinstance(handlers, list):
                handlers = [handlers]
                self._config[symbol_path] = handlers
                
            for handler in handlers:
                if not isinstance(handler, dict):
                    logger.warning(f"Invalid handler config for {symbol_path}: {handler}")
                    continue
                    
                # 填充默认值
                handler.setdefault('type', 'wrap')
                handler.setdefault('enabled', True)
                handler.setdefault('need_locals', False)
                handler.setdefault('lock_patch', False)
                handler.setdefault('metrics', [])
                
                # 确保metrics是列表
                if not isinstance(handler.get('metrics'), list):
                    handler['metrics'] = [handler['metrics']] if handler['metrics'] else []
                    
    def get_config(self) -> Dict[str, List[dict]]:
        """
        获取当前配置
        
        Returns:
            当前配置字典
        """
        return self._config
        
    def get_symbol_config(self, symbol_path: str) -> List[dict]:
        """
        获取指定symbol的配置
        
        Args:
            symbol_path: symbol路径
            
        Returns:
            symbol的handler配置列表，如果不存在返回空列表
        """
        return self._config.get(symbol_path, [])
