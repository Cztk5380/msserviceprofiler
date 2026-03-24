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
"""插件管理模块

提供基于 entry_points 的插件发现与加载机制，支持：
- 自动发现注册的插件
- 按名称过滤插件
- 插件加载状态追踪
"""
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, Iterable, Optional

from loguru import logger


class PluginState(Enum):
    """插件状态枚举"""
    DISCOVERED = auto()
    LOADED = auto()
    FAILED = auto()
    EXECUTED = auto()


@dataclass
class PluginInfo:
    """插件信息封装"""
    name: str
    entry_point: object
    state: PluginState = PluginState.DISCOVERED
    func: Optional[Callable] = None
    error: Optional[Exception] = None


@dataclass
class PluginRegistry:
    """插件注册表，管理插件生命周期"""
    group: str
    _plugins: Dict[str, PluginInfo] = field(default_factory=dict)
    _initialized: bool = False

    def discover(self) -> int:
        """发现并注册所有插件，返回发现的插件数量
        
        Raises:
            RuntimeError: entry_points 解析失败时抛出
        """
        if self._initialized:
            return len(self._plugins)
        
        try:
            entry_points_func = self._resolve_entry_points()
            eps = entry_points_func(group=self.group)
        except Exception as e:
            self._initialized = True  # 防止重复尝试
            logger.error(f"PluginRegistry[{self.group}]: failed to resolve entry_points: {e}")
            raise RuntimeError(f"Failed to resolve entry_points for group '{self.group}'") from e
        
        for ep in eps:
            self._plugins[ep.name] = PluginInfo(name=ep.name, entry_point=ep)
        
        self._initialized = True
        count = len(self._plugins)
        if count == 0:
            logger.debug(f"PluginRegistry[{self.group}]: no plugins discovered")
        else:
            logger.info(f"PluginRegistry[{self.group}]: discovered {count} plugin(s)")
            for name in self._plugins:
                logger.info(f"  -> {name}")
        
        return count

    def load(self, names: Optional[Iterable[str]] = None) -> Dict[str, Callable]:
        """加载插件，返回成功加载的插件函数字典
        
        Args:
            names: 指定加载的插件名，None 表示加载全部
            
        Returns:
            成功加载的插件字典，不包含加载失败的插件
            
        Note:
            此方法不会抛出异常，所有异常都会被捕获并记录日志
        """
        try:
            self.discover()
        except RuntimeError:
            return {}
        
        target_names = set(names) if names else set(self._plugins.keys())
        loaded: Dict[str, Callable] = {}
        
        for name in target_names:
            if name not in self._plugins:
                logger.warning(f"PluginRegistry[{self.group}]: plugin '{name}' not found")
                continue
            
            info = self._plugins[name]
            
            # 已加载过的插件直接返回缓存的函数
            if info.state == PluginState.LOADED and info.func is not None:
                loaded[name] = info.func
                continue
            
            # 已失败的插件跳过
            if info.state == PluginState.FAILED:
                continue
            
            try:
                loaded_func = info.entry_point.load()
                if loaded_func is None:
                    raise ValueError(f"entry_point.load() returned None for '{name}'")
                info.func = loaded_func
                info.state = PluginState.LOADED
                loaded[name] = loaded_func
                logger.info(f"PluginRegistry[{self.group}]: loaded '{name}'")
            except Exception as e:
                info.state = PluginState.FAILED
                info.error = e
                logger.exception(f"PluginRegistry[{self.group}]: failed to load '{name}'")
        
        return loaded

    def execute(self, names: Optional[Iterable[str]] = None) -> int:
        """执行插件函数，返回成功执行的数量
        
        Args:
            names: 指定执行的插件名，None 表示执行全部已加载的插件
            
        Returns:
            成功执行的插件数量
            
        Note:
            此方法不会抛出异常，所有异常都会被捕获并记录日志
        """
        try:
            plugins = self.load(names)
        except Exception as e:
            logger.exception(f"PluginRegistry[{self.group}]: unexpected error during load: {e}")
            return 0
        
        success = 0
        for name, func in plugins.items():
            if func is None:
                logger.warning(f"PluginRegistry[{self.group}]: skipping '{name}' with None function")
                continue
            try:
                func()
                if name in self._plugins:
                    self._plugins[name].state = PluginState.EXECUTED
                success += 1
            except Exception as e:
                if name in self._plugins:
                    self._plugins[name].error = e
                logger.exception(f"PluginRegistry[{self.group}]: failed to execute '{name}'")
        
        return success

    @staticmethod
    def _resolve_entry_points():
        """解析 entry_points 函数入口"""
        if sys.version_info >= (3, 10):
            from importlib.metadata import entry_points
        else:
            from importlib_metadata import entry_points  # type: ignore
        return entry_points


# 全局注册表缓存，按 group 维度隔离
_registry_cache: Dict[str, PluginRegistry] = {}


def get_plugin_registry(group: str = 'ms_serviceparam_optimizer.plugins') -> PluginRegistry:
    """获取插件注册表单例（按 group 隔离）
    
    不同 group 拥有独立的注册表实例，避免多插件组场景下状态污染。
    """
    if group not in _registry_cache:
        _registry_cache[group] = PluginRegistry(group=group)
    return _registry_cache[group]


def load_plugins_by_group(group: str, names: Optional[Iterable[str]] = None) -> Dict[str, Callable]:
    """加载指定组的插件
    
    Args:
        group: 插件组名称
        names: 可选的插件名称过滤
        
    Returns:
        加载成功的插件字典
    """
    registry = PluginRegistry(group=group)
    return registry.load(names)


def load_general_plugins() -> None:
    """加载并执行所有通用插件
    
    注意：插件可能在不同进程中被多次调用，
    请确保插件实现支持幂等执行。
    """
    registry = get_plugin_registry()
    registry.execute()
