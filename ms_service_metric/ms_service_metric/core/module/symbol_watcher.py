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
"""SymbolWatcher: 模块加载/卸载监视器（单例）

职责：
- 监听Python模块的导入事件
- 当模块加载或卸载时通知注册的回调
- 按模块管理回调，确保回调时就是确认的模块被加载

使用示例：
    watcher = SymbolWatcher()  # 多次调用返回同一个实例
    watcher.watch_module('module.name', my_callback)
    watcher.start()

    # 在回调中处理模块事件
    def my_callback(event):
        if event.type == ModuleEventType.LOADED:
            logger.info(f"Module {event.module_name} loaded")
"""

import importlib
import importlib.abc
import importlib.machinery as _machinery
import sys
import threading
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

import jsonschema

from ms_service_metric.utils.logger import get_logger

logger = get_logger("symbol_watcher")


class ModuleEventType(Enum):
    """模块事件类型"""
    LOADED = "loaded"
    UNLOADED = "unloaded"


class ModuleEvent:
    """模块事件
    
    Attributes:
        module_name: 模块名称
        type: 事件类型（加载/卸载）
        module: 模块对象（加载事件时有值）
    """
    
    def __init__(self, module_name: str, event_type: ModuleEventType, module=None):
        self.module_name = module_name
        self.type = event_type
        self.module = module
        
    def __repr__(self):
        return f"ModuleEvent({self.module_name}, {self.type.value})"


class SymbolWatchFinder(importlib.abc.MetaPathFinder):
    """模块导入监听器
    
    通过插入到sys.meta_path来监听模块导入事件。
    当目标模块被导入完成时，触发回调通知。
    """
    
    def __init__(self, watcher: "SymbolWatcher"):
        """
        初始化Finder
        
        Args:
            watcher: SymbolWatcher实例，用于通知事件
        """
        self._watcher = watcher
        self._target_modules: Set[str] = set()  # 需要监听的模块集合
        
    def add_target_module(self, module_name: str):
        """添加目标模块"""
        self._target_modules.add(module_name)
        logger.debug(f"Added target module: {module_name}")
        
    def remove_target_module(self, module_name: str):
        """移除目标模块"""
        self._target_modules.discard(module_name)
        logger.debug(f"Removed target module: {module_name}")
        
    def find_module(self, fullname: str, path=None):
        """查找模块（旧版Python兼容）"""
        return None
        
    def find_spec(self, fullname: str, path, target=None):
        """查找模块spec（Python 3.4+）

        包装模块的loader，在模块加载完成后触发回调。
        """
        if not self._should_watch_module(fullname):
            return None

        # 使用PathFinder查找spec
        spec = _machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec

        # 检查是否已经被包装过
        if getattr(spec.loader, "_symbol_watcher_wrapped", False):
            return spec

        orig_loader = spec.loader
        finder = self  # 保存finder引用

        class LoaderWrapper(importlib.abc.Loader):
            """Loader包装器，在exec_module后触发回调"""
            _symbol_watcher_wrapped = True

            def __getattr__(self, name):
                """代理原始loader的所有属性"""
                return getattr(orig_loader, name)

            def create_module(self, mod_spec):
                if hasattr(orig_loader, "create_module"):
                    return orig_loader.create_module(mod_spec)
                return None

            def exec_module(self, module):
                logger.debug(f"Executing module: {module.__name__}")
                # 先执行原始loader加载模块
                orig_loader.exec_module(module)
                # 模块加载完成后通知watcher
                finder._watcher._notify_module_loaded(module.__name__)

        # 替换loader
        spec.loader = LoaderWrapper()
        logger.debug(f"Wrapped loader for module: {fullname}")
        return spec

    def _should_watch_module(self, fullname: str) -> bool:
        """检查是否应该监听该模块

        如果有全局回调，则监听所有模块；
        否则只监听目标模块或其子模块。
        """
        # 如果有全局回调，监听所有模块
        if self._watcher.has_global_callbacks():
            return True

        # 检查是否是目标模块或其子模块
        for target in self._target_modules:
            if fullname == target or fullname.startswith(target + '.'):
                return True
        return False


class SymbolWatcher:
    """Symbol监视器（单例）

    负责监听模块加载/卸载事件，并按模块管理回调。
    确保回调触发时就是确认的模块被加载了。

    多次实例化返回同一个对象，确保全局只有一个监视器实例。

    Attributes:
        _finder: 模块导入监听器
        _module_callbacks: 按模块管理的回调字典
        _loaded_modules: 已加载的模块集合
        _installed: 是否已安装到sys.meta_path
        _instance: 单例实例
        _initialized: 是否已初始化
    """

    _instance: Optional["SymbolWatcher"] = None
    _initialized: bool = False
    _singleton_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "SymbolWatcher":
        """确保只有一个实例"""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化SymbolWatcher（仅第一次调用有效）"""
        # 避免重复初始化
        if SymbolWatcher._initialized:
            return

        with SymbolWatcher._singleton_lock:
            if SymbolWatcher._initialized:
                return

            self._finder = SymbolWatchFinder(self)
            # key: module_name, value: list of callbacks
            self._module_callbacks: Dict[str, List[Callable[[ModuleEvent], None]]] = {}
            # 全局回调列表，监听所有模块
            self._global_callbacks: List[Callable[[str], None]] = []
            self._loaded_modules: Set[str] = set()
            self._installed = False
            self._lock = threading.Lock()

            # 初始化已加载的模块
            self._init_loaded_modules()

            SymbolWatcher._initialized = True
            logger.debug("SymbolWatcher initialized")
        
    def _init_loaded_modules(self):
        """初始化已加载模块集合"""
        # 记录当前已加载的所有模块
        for name in sys.modules.keys():
            self._loaded_modules.add(name)
            
    def watch(self, callback: Callable[[str], None]):
        """
        监听所有模块的加载事件

        注册一个全局回调函数，任何模块被加载时都会触发该回调。
        回调函数接收模块名称作为参数。

        Args:
            callback: 回调函数，接收module_name参数
        """
        with self._lock:
            if callback not in self._global_callbacks:
                self._global_callbacks.append(callback)
                logger.debug(f"Global callback registered: {callback}")

    def unwatch(self, callback: Callable[[str], None]):
        """
        取消监听所有模块的加载事件

        Args:
            callback: 要注销的全局回调函数
        """
        with self._lock:
            if callback in self._global_callbacks:
                self._global_callbacks.remove(callback)
                logger.debug(f"Global callback unregistered: {callback}")

    def has_global_callbacks(self) -> bool:
        """
        检查是否有注册的全局回调

        Returns:
            如果有全局回调返回True
        """
        with self._lock:
            return len(self._global_callbacks) > 0

    def watch_module(self, module_name: str, callback: Callable[[ModuleEvent], None]):
        """
        监听指定模块的事件

        注册回调并立即检查模块是否已加载，如果已加载会立即触发回调。
        回调触发时确认就是该模块被加载了，不需要在回调中再检查模块名。

        Args:
            module_name: 要监听的模块名称
            callback: 回调函数，接收ModuleEvent参数
        """
        with self._lock:
            # 添加到目标模块
            self._finder.add_target_module(module_name)

            # 注册回调
            if module_name not in self._module_callbacks:
                self._module_callbacks[module_name] = []
            if callback not in self._module_callbacks[module_name]:
                self._module_callbacks[module_name].append(callback)
                logger.debug(f"Callback registered for module {module_name}: {callback}")

        # 如果模块已加载，立即触发回调
        if self.is_module_loaded(module_name):
            module = sys.modules.get(module_name)
            event = ModuleEvent(module_name, ModuleEventType.LOADED, module)
            try:
                callback(event)
                logger.debug(f"Immediate callback triggered for already loaded module: {module_name}")
            except Exception as e:
                logger.error(f"Error in immediate callback for {module_name}: {e}")
                
    def unwatch_module(self, module_name: str, callback: Callable[[ModuleEvent], None]):
        """
        取消监听指定模块的事件
        
        Args:
            module_name: 模块名称
            callback: 要注销的回调函数
        """
        with self._lock:
            if module_name in self._module_callbacks:
                if callback in self._module_callbacks[module_name]:
                    self._module_callbacks[module_name].remove(callback)
                    logger.debug(f"Callback unregistered for module {module_name}: {callback}")
                
                # 如果没有回调了，移除目标模块
                if not self._module_callbacks[module_name]:
                    del self._module_callbacks[module_name]
                    self._finder.remove_target_module(module_name)
                    
    def start(self):
        """
        启动监视器

        将finder插入到sys.meta_path中，开始监听模块导入。
        多次调用只会启动一次。
        """
        if self._installed:
            logger.debug("SymbolWatcher already started")
            return

        with self._lock:
            if self._installed:
                logger.debug("SymbolWatcher already started")
                return

            # 插入到sys.meta_path开头，确保最先处理
            sys.meta_path.insert(0, self._finder)
            self._installed = True

        logger.info("SymbolWatcher started")
        
    def uninstall(self):
        """
        卸载监视器
        
        从sys.meta_path中移除finder，停止监听。
        """
        if not self._installed:
            return
            
        # 从sys.meta_path中移除
        if self._finder in sys.meta_path:
            sys.meta_path.remove(self._finder)
            
        self._installed = False
        logger.info("SymbolWatcher uninstalled")
        
    def is_module_loaded(self, module_name: str) -> bool:
        """
        检查模块是否已加载

        Args:
            module_name: 模块名称

        Returns:
            如果模块已加载返回True
        """
        return module_name in sys.modules
        
    def get_loaded_modules(self) -> Set[str]:
        """
        获取已加载的模块集合
        
        Returns:
            已加载模块名称集合
        """
        return set(self._loaded_modules)
        
    def _notify_module_loaded(self, module_name: str):
        """
        通知模块加载事件

        通知注册了该模块的回调，以及所有全局回调。

        Args:
            module_name: 模块名称
        """
        logger.debug(f"Module loaded: {module_name}")
        # 添加到已加载集合
        self._loaded_modules.add(module_name)

        # 创建事件
        module = sys.modules.get(module_name)
        event = ModuleEvent(module_name, ModuleEventType.LOADED, module)

        # 通知全局回调（传入module_name）
        with self._lock:
            global_callbacks = self._global_callbacks.copy()

        for callback in global_callbacks:
            try:
                callback(module_name)
            except Exception as e:
                logger.error(f"Error in global callback for {module_name}: {e}")

        # 通知注册了该模块的回调
        with self._lock:
            callbacks = self._module_callbacks.get(module_name, []).copy()

        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in callback for {module_name}: {e}")
                
    def _notify_module_unloaded(self, module_name: str):
        """
        通知模块卸载事件
        
        Args:
            module_name: 模块名称
        """
        # 从已加载集合移除
        self._loaded_modules.discard(module_name)
        
        # 创建事件
        event = ModuleEvent(module_name, ModuleEventType.UNLOADED)
        
        # 只通知注册了该模块的回调
        with self._lock:
            callbacks = self._module_callbacks.get(module_name, []).copy()
            
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in callback for {module_name}: {e}")
                
    def stop(self):
        """
        停止监视器
        
        卸载finder并清理资源。
        """
        self.uninstall()
        logger.debug("SymbolWatcher stopped")
