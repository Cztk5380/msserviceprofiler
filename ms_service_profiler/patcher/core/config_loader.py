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
ConfigLoader: 加载 YAML 配置并解析为 Handler 列表。

职责：
- 读取 config_path 对应的 yml 文件
- 将配置解析为以 symbol 为键、Handler 列表为值的结构
- 支持 yml 中配置的 handler 或默认 handler（make_default_time_hook）
"""

import importlib
from typing import Dict, List, Optional, Tuple, Any, Callable

from .utils import load_yaml_config
from .logger import logger
from .dynamic_hook import make_default_time_hook, DynamicHooker, ConfigHooker
from .metric_hook import wrap_handler_with_metrics
import json


def _parse_symbol_path(symbol_path: str) -> Tuple[str, str, Optional[str]]:
    """解析 symbol 路径，返回 (module_path, method_name, class_name)。"""
    if ':' not in symbol_path:
        logger.warning(f"Invalid symbol path format: {symbol_path}")
        return '', '', None
    module_path, class_method = symbol_path.split(':', 1)
    if '.' in class_method:
        class_name, method_name = class_method.split('.', 1)
        return module_path, method_name, class_name
    return module_path, class_method, None


def _build_hook_points(module_path: str, method_name: str, class_name: Optional[str]) -> List[Tuple[str, str]]:
    """构建 hook 点列表。"""
    hook_point = f"{class_name}.{method_name}" if class_name else method_name
    return [(module_path, hook_point)]


def _resolve_handler_func(symbol_info: dict, method_name: str) -> Callable:
    """根据配置解析 handler 函数。
    
    若 yml 中定义了 handler 则导入使用；否则使用 make_default_time_hook 生成默认 handler。
    """
    handler_path = symbol_info.get('handler')
    
    if not handler_path:
        domain = symbol_info.get('domain', 'Default')
        name = symbol_info.get('name', method_name)
        attributes = symbol_info.get('attributes')
        return make_default_time_hook(domain=domain, name=name, attributes=attributes)
    
    # 自定义 handler: "module.path:func_name"
    if isinstance(handler_path, str) and ':' in handler_path:
        try:
            mod_str, func_name = handler_path.split(':', 1)
            mod_obj = importlib.import_module(mod_str)
            func = getattr(mod_obj, func_name, None)
            if callable(func):
                return func
            logger.warning(f"Handler '{handler_path}' is not callable, using default")
        except Exception as e:
            logger.warning(f"Failed to import handler '{handler_path}': {e}, using default")
    
    domain = symbol_info.get('domain', 'Default')
    name = symbol_info.get('name', method_name)
    attributes = symbol_info.get('attributes')
    return make_default_time_hook(domain=domain, name=name, attributes=attributes)


def _metrics_noop_handler(original_func, *args, **kwargs):
    """供 metrics 使用的透传 handler，无 handler_path 时仅由 wrap_handler_with_metrics 封装。"""
    return original_func(*args, **kwargs)


def _resolve_metrics_handler_func(symbol_info: dict, method_name: str) -> Callable:
    """解析 metrics 配置的 handler：无 handler_path 时用 wrap_handler_with_metrics 封装透传函数；
    有 handler_path 且为 "module:func" 时导入并直接返回该函数（不再包装）。
    """
    handler_path = symbol_info.get('handler')
    if not handler_path:
        return wrap_handler_with_metrics(_metrics_noop_handler, symbol_info)
    if isinstance(handler_path, str) and ':' in handler_path:
        try:
            mod_str, func_name = handler_path.split(':', 1)
            mod_obj = importlib.import_module(mod_str)
            func = getattr(mod_obj, func_name, None)
            if callable(func):
                return func
            logger.warning(f"Metrics handler '{handler_path}' is not callable, using wrap_handler_with_metrics")
        except Exception as e:
            logger.warning(f"Failed to import metrics handler '{handler_path}': {e}, using wrap_handler_with_metrics")
    return wrap_handler_with_metrics(_metrics_noop_handler, symbol_info)


class ConfigLoader:
    """配置加载器：读取 yml 文件，返回以 symbol 为粒度的 Handler 列表。
    
    将 yml 配置加载为 handler 列表，以 handler 为粒度，每个 handler 对应自己的 symbol。
    - 若 yml 中对同一 symbol 配置了多个 handler，则放在同一列表中
    - 若 yml 中只定义了 symbol 而未定义 handler，则使用 make_default_time_hook 生成默认 handler
    - Handler 为 DynamicHooker 类实例（继承自 VLLMHookerBase，类似 AutoHooker）
    
    Attributes:
        _config_path: 配置文件路径
    """
    
    def __init__(self, config_path: str):
        """初始化 ConfigLoader。
        
        Args:
            config_path: yml 配置文件路径
        """
        self._config_path = config_path
    
    def load_profiling(self) -> Optional[Dict[str, List[ConfigHooker]]]:
        """加载 profiling yml 配置并解析为 Handler 列表。
        
        Returns:
            Dict[str, List[DynamicHooker]]: symbol_path -> Handler 列表。
                同一 symbol 若有多个 handler 配置，则在该 symbol 的列表中包含多个 Handler。
        """
        raw_config = load_yaml_config(self._config_path)
        if not raw_config:
            return {}
        
        if not isinstance(raw_config, list):
            logger.warning("Config should be a list of symbol configurations")
            return {}
        
        result: Dict[str, List[ConfigHooker]] = {}
        
        for item in raw_config:
            if not isinstance(item, dict) or 'symbol' not in item:
                logger.warning("Skip invalid config item: missing 'symbol'")
                continue
            
            symbol_path = item['symbol']
            module_path, method_name, class_name = _parse_symbol_path(symbol_path)
            if not module_path:
                continue
            
            hook_points = _build_hook_points(module_path, method_name, class_name)
            handler_func = _resolve_handler_func(item, method_name)
            
            handler_instance = ConfigHooker(
                hook_list=hook_points,
                symbol_path=symbol_path,
                hook_func=handler_func,
                min_version=item.get('min_version'),
                max_version=item.get('max_version'),
                caller_filter=item.get('caller_filter'),
                need_locals="expr" in json.dumps(item) or "handler" in json.dumps(item),
            )
            
            if symbol_path not in result:
                result[symbol_path] = []
            result[symbol_path].append(handler_instance)
        
        logger.debug(f"ConfigLoader loaded {len(result)} profiling symbols from {self._config_path}")
        return result

    def load_metrics(self) -> Optional[Dict[str, List[ConfigHooker]]]:
        """加载 metrics yml 并解析为 Handler 列表（每个 handler 经 wrap_handler_with_metrics 包装）。

        Returns:
            Dict[str, List[DynamicHooker]]: symbol_path -> Handler 列表，格式与 load() 一致。
        """
        raw_config = load_yaml_config(self._config_path)
        if not raw_config:
            return {}
        if not isinstance(raw_config, list):
            logger.warning("Metrics config should be a list of symbol configurations")
            return {}
        result: Dict[str, List[ConfigHooker]] = {}
        for item in raw_config:
            if not isinstance(item, dict) or 'symbol' not in item:
                logger.warning("Skip invalid metrics config item: missing 'symbol'")
                continue
            symbol_path = item['symbol']
            module_path, method_name, class_name = _parse_symbol_path(symbol_path)
            if not module_path:
                continue
            hook_points = _build_hook_points(module_path, method_name, class_name)
            handler_func = _resolve_metrics_handler_func(item, method_name)
            handler_instance = ConfigHooker(
                hook_list=hook_points,
                symbol_path=symbol_path,
                hook_func=handler_func,
                min_version=item.get('min_version'),
                max_version=item.get('max_version'),
                caller_filter=item.get('caller_filter'),
                need_locals="expr" in json.dumps(item) or "handler" in json.dumps(item),
            )
            if symbol_path not in result:
                result[symbol_path] = []
            result[symbol_path].append(handler_instance)
        logger.debug(f"ConfigLoader loaded {len(result)} metrics symbols from {self._config_path}")
        return result
