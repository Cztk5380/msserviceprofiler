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

import importlib
import importlib.abc
import importlib.machinery as _machinery
import sys
import threading
from typing import Dict, Any, List, Tuple, Optional, Callable
from .logger import logger
from .dynamic_hook import make_default_time_hook, register_dynamic_hook


class SymbolWatchFinder(importlib.abc.MetaPathFinder):
    """监听配置中的 symbol 模块导入，动态应用 hooks。
    
    该类继承自 importlib.abc.MetaPathFinder，实现模块导入监听功能：
    - 监听目标模块的导入事件
    - 动态应用配置的 hooks
    - 避免重复应用 hooks
    - 支持父包导入监听
    
    Attributes:
        _symbol_hooks (Dict): symbol 配置字典
        _config_loaded (bool): 配置是否已加载
        _applied_hooks (Set): 已应用的 hook 集合
    """
    
    def __init__(self):
        """初始化 SymbolWatchFinder。"""
        self._symbol_hooks = {}
        self._config_loaded = False
        self._applied_hooks = set()  # 记录已应用的 hook，避免重复
        self._prepared_hookers = []  # 存储准备好但未应用的 hooker 实例
        self._applied_hookers = []   # 已实际 init() 应用过的 hooker（用于 disable 时 recover）
        self._symbol_to_hooker = {}  # 映射：symbol_path -> hooker 实例
        self._auto_apply_enabled = False
        self._lock = threading.Lock()

    def set_auto_apply(self, enabled: bool):
        """设置是否在 hook 准备完成后立刻应用（init）。"""
        self._auto_apply_enabled = bool(enabled)

    def get_applied_hookers(self):
        """获取所有已实际应用过的 hookers（会随运行增长）。"""
        with self._lock:
            return list(self._applied_hookers)
    
    def recover_hookers_for_symbols(self, symbol_paths: set):
        """恢复指定 symbol 路径对应的已应用 hookers。
        
        Args:
            symbol_paths: 需要恢复的 symbol 路径集合
        """
        with self._lock:
            hookers_to_recover = []
            for symbol_path in symbol_paths:
                if symbol_path in self._symbol_to_hooker:
                    hooker = self._symbol_to_hooker[symbol_path]
                    if hooker in self._applied_hookers:
                        hookers_to_recover.append(hooker)
            
            for hooker in hookers_to_recover:
                try:
                    for hook_helper in hooker.hooks:
                        hook_helper.recover()
                    logger.debug(f"Recovered hooker for removed symbol")
                except Exception as e:
                    logger.error(f"Failed to recover hooker: {e}")
    
    def load_symbol_config(self, config_data: List[Dict[str, Any]], hooks_enabled: bool = False):
        """加载 symbol 配置。
        
        Args:
            config_data: 配置数据列表
            hooks_enabled: hooks 是否当前已启用，如果为 True 且配置中有删除的 symbol，
                          会立即恢复对应的已应用 hookers
        """
        # 收集新配置中的所有 symbol 路径
        new_symbol_paths = set()
        for symbol_config in config_data:
            if isinstance(symbol_config, dict) and 'symbol' in symbol_config:
                new_symbol_paths.add(symbol_config['symbol'])
        
        # 清理不再存在于新配置中的 symbol 的相关记录
        if self._config_loaded:
            removed_symbols = self._applied_hooks - new_symbol_paths
            if removed_symbols:
                logger.debug(f"Removing {len(removed_symbols)} symbols from config (no longer in new config)")
                
                # 清理 applied_hooks 记录
                self._applied_hooks -= removed_symbols
                
                # 清理 prepared_hookers 和 applied_hookers 中对应的 hookers
                with self._lock:
                    prepared_hookers_to_remove = []
                    applied_hookers_to_remove = []
                    
                    for symbol_path in removed_symbols:
                        if symbol_path in self._symbol_to_hooker:
                            hooker = self._symbol_to_hooker[symbol_path]
                            
                            # 无论 hooker 是否已应用，都从 prepared_hookers 中移除
                            # 这样 apply_all_hooks 时不会重新应用被删除的 symbol
                            if hooker in self._prepared_hookers:
                                prepared_hookers_to_remove.append(hooker)
                            
                            # 如果 hooker 已经应用，也需要从 applied_hookers 中移除
                            if hooker in self._applied_hookers:
                                applied_hookers_to_remove.append(hooker)
                            
                            # 从映射中移除
                            del self._symbol_to_hooker[symbol_path]
                    
                    # 从 prepared_hookers 中移除被删除 symbol 对应的 hookers
                    for hooker in prepared_hookers_to_remove:
                        self._prepared_hookers.remove(hooker)
                        logger.debug(f"Removed prepared hooker for removed symbol")
                    
                    # 处理已应用的 hookers
                    if hooks_enabled and applied_hookers_to_remove:
                        # 如果 hooks 当前已启用，立即恢复这些 hookers
                        logger.debug(f"Recovering {len(applied_hookers_to_remove)} applied hookers for removed symbols (hooks currently enabled)")
                        for hooker in applied_hookers_to_remove:
                            try:
                                for hook_helper in hooker.hooks:
                                    hook_helper.recover()
                                logger.debug(f"Recovered hooker for removed symbol")
                            except Exception as e:
                                logger.error(f"Failed to recover hooker: {e}")
                    
                    # 从 applied_hookers 中移除已应用的 hookers
                    for hooker in applied_hookers_to_remove:
                        self._applied_hookers.remove(hooker)
                        if hooks_enabled:
                            logger.debug(f"Removed applied hooker for removed symbol (already recovered)")
                        else:
                            logger.debug(f"Removed applied hooker for removed symbol (will be recovered on disable)")
                    
                    total_removed = len(prepared_hookers_to_remove) + len(applied_hookers_to_remove)
                    if total_removed > 0:
                        logger.debug(f"Removed {total_removed} hookers ({len(prepared_hookers_to_remove)} prepared, {len(applied_hookers_to_remove)} applied) for removed symbols")
        
        self._symbol_hooks = {}
        for i, symbol_config in enumerate(config_data):
            symbol_id = f"symbol_{i}"
            # 确保 symbol_config 是字典且包含必要的信息
            if not isinstance(symbol_config, dict):
                logger.warning(f"Invalid symbol config at index {i}, expected dict, got {type(symbol_config)}")
                continue
                
            # 确保包含 'symbol' 键
            if 'symbol' not in symbol_config:
                logger.warning(f"Symbol config at index {i} missing 'symbol' key")
                continue
                
            # 创建配置的深拷贝，避免原始配置被修改
            self._symbol_hooks[symbol_id] = symbol_config.copy()  # 使用 copy() 避免引用问题
        
        self._config_loaded = True
        logger.debug(f"Loaded {len(self._symbol_hooks)} symbol configurations")
    
    def find_spec(self, fullname, path, target=None):
        """查找模块规范，实现模块导入监听。
        
        Args:
            fullname: 完整模块名
            path: 搜索路径
            target: 目标对象
            
        Returns:
            Optional[ModuleSpec]: 模块规范，非目标模块返回 None
        """
        # 检查是否是配置中的 symbol 模块
        if not self._is_target_symbol(fullname):
            return None
            
        # 委托给标准 PathFinder
        spec = _machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec

        # 避免重复包装
        if getattr(spec.loader, "_vllm_profiler_wrapped", False):
            return spec

        orig_loader = spec.loader

        class LoaderWrapper(importlib.abc.Loader):
            _vllm_profiler_wrapped = True

            def create_module(self, spec):
                if hasattr(orig_loader, "create_module"):
                    return orig_loader.create_module(spec)
                return None

            def exec_module(self, module):
                orig_loader.exec_module(module)
                # 调用外层类的方法
                self._finder._on_symbol_module_loaded(fullname)

        wrapper = LoaderWrapper()
        wrapper._finder = self
        spec.loader = wrapper
        return spec
    
    def _is_target_symbol(self, fullname):
        """检查是否是配置中的目标 symbol 模块。
        
        Args:
            fullname: 完整模块名
            
        Returns:
            bool: 如果是目标模块则返回 True
        """
        if not self._config_loaded:
            return False
        
        # 检查是否匹配配置中的任何 symbol
        for symbol_info in self._symbol_hooks.values():
            symbol_path = symbol_info['symbol']
            # 提取模块路径（去掉类名和方法名）
            module_path = symbol_path.split(':')[0]
            if fullname == module_path:
                logger.debug(f"SymbolWatchFinder: Direct match for {fullname} -> {symbol_path}")
                return True
            # 同时监听父包导入事件：当父包被加载时，后续子模块导入仍会触发
            if module_path.startswith(fullname + "."):
                logger.debug(f"SymbolWatchFinder: Parent package match for {fullname} -> {symbol_path}")
                return True
        return False
    
    def _on_symbol_module_loaded(self, fullname: str):
        """当 symbol 模块加载完成时的回调。
        
        Args:
            fullname: 完整模块名
        """
        logger.debug(f"SymbolWatchFinder: Module loaded callback for {fullname}")
        # 委托给 _prepare_hooks_for_module
        self._prepare_hooks_for_module(fullname)
    
    def _prepare_hooks_for_module(self, fullname: str):
        """准备模块的 hooks（但不立即应用）。
        
        Args:
            fullname: 完整模块名
        """
        # 找到该模块对应的所有 symbols
        module_symbols = []
        for symbol_id, symbol_info in self._symbol_hooks.items():
            symbol_path = symbol_info['symbol']
            module_path = symbol_path.split(':')[0]
            if fullname == module_path:
                module_symbols.append((symbol_id, {"symbol": symbol_info.get("symbol")}))
            # 若当前加载的是父包，尝试安全导入子模块以触发后续事件
            elif module_path.startswith(fullname + "."):
                try:
                    importlib.import_module(module_path)
                except Exception as e:
                    logger.debug(f"Failed to import {module_path}: {e}")
        
        if module_symbols:
            logger.debug(f"Detected symbol module loaded: {fullname}, preparing {len(module_symbols)} hooks")
            for _, symbol_info in module_symbols:
                logger.debug(f"  - Preparing hook for {symbol_info['symbol']}")
            self._prepare_symbol_hooks_for_module(fullname, module_symbols)
    
    def _prepare_symbol_hooks_for_module(self, module_name: str, module_symbols: List[Tuple[str, Dict[str, Any]]]):
        """为特定模块准备 symbol hooks（但不立即应用）。
        
        Args:
            module_name: 模块名称
            module_symbols: 模块对应的 symbol 列表
        """
        try:
            for symbol_id, _ in module_symbols:
                full_info = self._symbol_hooks.get(symbol_id, {})
                self._prepare_single_symbol_hook(symbol_id, full_info)
                
        except Exception as e:
            logger.error(f"Failed to prepare symbol hooks for module {module_name}: {e}")
    
    def _parse_symbol_path(self, symbol_path: str) -> Tuple[str, str, Optional[str]]:
        """解析 symbol 路径，返回 (module_path, method_name, class_name)。
        
        Args:
            symbol_path: symbol 路径字符串
            
        Returns:
            Tuple[str, str, Optional[str]]: (模块路径, 方法名, 类名)
        """
        module_path, class_method = symbol_path.split(':')
        if '.' in class_method:
            class_name, method_name = class_method.split('.')
            return module_path, method_name, class_name
        else:
            return module_path, class_method, None

    def _create_handler_function(self, symbol_info: dict, method_name: str) -> Callable:
        """创建处理函数，支持自定义 handler 或默认 timer。
        
        Args:
            symbol_info: symbol 配置信息
            method_name: 方法名称
            
        Returns:
            Callable: 处理函数
        """
        handler_path = symbol_info.get('handler')
        
        if not handler_path:
            logger.debug(f"No handler specified for symbol {symbol_info['symbol']}, using default timer")
            return make_default_time_hook(
                domain=symbol_info.get('domain', "Default"),
                name=symbol_info.get('name', method_name),
                attributes=symbol_info.get('attributes')
            )
        else:
            # 解析自定义 handler
            handler_module, handler_func = handler_path.split(':')
            handler_module_obj = importlib.import_module(handler_module)
            return getattr(handler_module_obj, handler_func)

    def _build_hook_points(
            self, module_path: str, method_name: str, class_name: Optional[str]
        ) -> List[Tuple[str, str]]:
        """构建 hook 点列表。
        
        Args:
            module_path: 模块路径
            method_name: 方法名称
            class_name: 类名称，可选
            
        Returns:
            List[Tuple[str, str]]: hook 点列表
        """
        hook_point = f"{class_name}.{method_name}" if class_name else method_name
        return [(module_path, hook_point)]

    def _register_hook_only(
            self, symbol_info: dict, hook_points: List[Tuple[str, str]], handler_func_obj: Callable
        ):
        """注册 hook（但不立即应用）。
        
        Args:
            symbol_info: symbol 配置信息
            hook_points: hook 点列表
            handler_func_obj: handler 函数对象
            
        Returns:
            DynamicHooker: 注册的 hooker 实例
        """
        # 注册动态 hook（但不调用 init()）
        hooker = register_dynamic_hook(
            hook_list=hook_points,
            hook_func=handler_func_obj,
            min_version=symbol_info.get('min_version'),
            max_version=symbol_info.get('max_version'),
            caller_filter=symbol_info.get('caller_filter')
        )
        
        # 不立即应用 hook，等待 apply_all_hooks() 调用
        return hooker
    
    def apply_all_hooks(self):
        """应用所有准备好的 hooks。
        
        Returns:
            List: 所有已应用的 hooker 实例列表
        """
        # enable 后：后续新 module 的 hook 也应自动应用
        self.set_auto_apply(True)

        logger.info(f"Applying {len(self._prepared_hookers)} prepared hooks...")
        applied_now = 0

        for hooker in list(self._prepared_hookers):
            try:
                hooker.init()
                with self._lock:
                    if hooker not in self._applied_hookers:
                        self._applied_hookers.append(hooker)
                applied_now += 1
                logger.debug(f"Applied hooker: {hooker.applied_hook_func_name}")
            except Exception as e:
                logger.error(f"Failed to apply hooker {hooker}: {e}")

        logger.info(f"Successfully applied {applied_now} hooks")
        return self.get_applied_hookers()

    def _prepare_single_symbol_hook(self, symbol_id: str, symbol_info: dict):
        """准备单个 symbol 的 hook（但不立即应用）。
        
        Args:
            symbol_id: symbol 标识符
            symbol_info: symbol 配置信息
        """
        try:
            symbol_path = symbol_info['symbol']
            
            # 检查是否已经准备过这个 hook
            if symbol_path in self._applied_hooks:
                logger.debug(f"Hook for {symbol_path} already prepared, skipping")
                return
            
            # 解析 symbol 路径
            module_path, method_name, class_name = self._parse_symbol_path(symbol_path)
            
            # 创建处理函数
            handler_func_obj = self._create_handler_function(symbol_info, method_name)
            
            # 构建 hook 点列表
            hook_points = self._build_hook_points(module_path, method_name, class_name)
            
            # 注册 hook（但不立即应用）
            hooker = self._register_hook_only(symbol_info, hook_points, handler_func_obj)
            
            # 保存 hooker 实例
            self._prepared_hookers.append(hooker)
            
            # 记录 symbol 到 hooker 的映射
            self._symbol_to_hooker[symbol_path] = hooker
            
            # 记录已准备的 hook
            self._applied_hooks.add(symbol_path)
            
            logger.debug(f"Prepared hook for symbol {symbol_path}")

            # 如果已经处于 enabled 状态，则模块一加载就应立即 apply（否则会出现“prepared 但不生效”）
            if self._auto_apply_enabled:
                try:
                    hooker.init()
                    with self._lock:
                        if hooker not in self._applied_hookers:
                            self._applied_hookers.append(hooker)
                    logger.debug(f"Auto-applied hook for symbol {symbol_path}")
                except Exception as e:
                    logger.error(f"Failed to auto-apply hook for symbol {symbol_path}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to prepare hook for symbol {symbol_path}: {e}")

    def check_and_apply_existing_modules(self) -> bool:
        """检查目标模块是否已经被导入，如果是则立即准备 hooks。
        
        遍历所有配置的 symbol，检查对应的模块是否已经加载，
        如果是则模拟模块加载完成事件以准备相应的 hooks。
        
        Returns:
            bool: 操作是否成功
        """
        logger.debug("Checking for already loaded modules...")
        for _, symbol_info in self._symbol_hooks.items():
            symbol_path = symbol_info["symbol"]
            module_path = symbol_path.split(":")[0]
            
            logger.debug(f"Checking module {module_path} for symbol {symbol_path}")
            logger.debug(f"  - Module in sys.modules: {module_path in sys.modules}")
            logger.debug(f"  - Symbol already prepared: {symbol_path in self._applied_hooks}")
            
            # 检查模块是否已导入，且该 symbol 尚未准备
            if module_path in sys.modules and symbol_path not in self._applied_hooks:
                logger.debug(f"Module {module_path} already loaded, preparing hooks")
                self._on_symbol_module_loaded(module_path)
        return True
