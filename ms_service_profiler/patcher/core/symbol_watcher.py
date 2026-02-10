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
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from .logger import logger

if TYPE_CHECKING:
    from .dynamic_hook import DynamicHooker


class SymbolWatchFinder(importlib.abc.MetaPathFinder):
    """监听配置中的 symbol 模块导入，动态应用 hooks。

    使用 ConfigLoader 加载的 Handler 列表，以 handler 为粒度监听模块导入并应用 hooks。

    Attributes:
        _symbol_handlers_profiling (Dict): symbol_path -> List[DynamicHooker]，profiling 配置
        _symbol_handlers_metrics (Dict): symbol_path -> List[DynamicHooker]，metrics 配置
        _config_loaded (bool): 配置是否已加载
        _applied_hooks (Set): 已准备的 symbol 集合
    """

    def __init__(self):
        """初始化 SymbolWatchFinder。"""
        self._symbol_handlers_profiling: Dict[str, List] = {}
        self._symbol_handlers_metrics: Dict[str, List] = {}
        self._config_loaded = False
        self._applied_hooks = set()
        self._prepared_hookers: List = []
        self._applied_hookers: List = []
        self._symbol_to_hooker: Dict[str, List] = {}
        self._auto_apply_enabled = False
        self._lock = threading.Lock()

    def set_auto_apply(self, enabled: bool):
        """设置是否在 hook 准备完成后立刻应用（init）。"""
        self._auto_apply_enabled = bool(enabled)

    def get_applied_hookers(self):
        """获取所有已实际应用过的 hookers。"""
        with self._lock:
            return list(self._applied_hookers)

    def _get_hookers_for_symbol(self, symbol_path: str) -> List:
        """获取 symbol 对应的 hooker 列表。"""
        val = self._symbol_to_hooker.get(symbol_path)
        if val is None:
            return []
        return val if isinstance(val, list) else [val]

    def recover_hookers_for_symbols(self, symbol_paths: set):
        """恢复指定 symbol 路径对应的已应用 hookers。"""
        with self._lock:
            hookers_to_recover = []
            for symbol_path in symbol_paths:
                for hooker in self._get_hookers_for_symbol(symbol_path):
                    if hooker in self._applied_hookers:
                        hookers_to_recover.append(hooker)

            for hooker in hookers_to_recover:
                try:
                    for hook_helper in hooker.hooks:
                        hook_helper.recover()
                    logger.debug("Recovered hooker for removed symbol")
                except Exception as e:
                    logger.error(f"Failed to recover hooker: {e}")

    def _get_combined_symbol_paths(self):
        """返回当前已加载的 profiling 与 metrics 的 symbol 路径并集。"""
        return set(self._symbol_handlers_profiling.keys()) | set(self._symbol_handlers_metrics.keys())

    def _get_handlers_for_symbol(self, symbol_path: str) -> List:
        """返回某 symbol 的 handler 列表，供后续 for 循环依次执行 hook。

        当 profiling 与 metrics 同时存在 handler 时，保证 _symbol_handlers_metrics 中的
        handler 排在后面，这样最终被 hook 替换的是 metrics 的 handler。
        """
        p = self._symbol_handlers_profiling.get(symbol_path) or []
        m = self._symbol_handlers_metrics.get(symbol_path) or []
        return p + m

    def load_handlers(
        self,
        profiling_handlers: Optional[Dict[str, List['DynamicHooker']]] = None,
        metrics_handlers: Optional[Dict[str, List['DynamicHooker']]] = None,
        hooks_enabled: bool = False,
    ):
        """加载 profiling 与 metrics 两路 Handler 列表，分别存储并分别参与后续处理。

        Args:
            profiling_handlers: symbol_path -> List[DynamicHooker]，由 ConfigLoader.load_profiling() 返回
            metrics_handlers: symbol_path -> List[DynamicHooker]，由 ConfigLoader.load_metrics() 返回
            hooks_enabled: hooks 是否当前已启用，用于配置变更时的恢复逻辑
        """
        profiling_handlers = profiling_handlers or {}
        metrics_handlers = metrics_handlers or {}
        new_symbol_paths = set(profiling_handlers.keys()) | set(metrics_handlers.keys())

        if self._config_loaded:
            removed_symbols = self._applied_hooks - new_symbol_paths
            if removed_symbols:
                logger.debug(f"Removing {len(removed_symbols)} symbols from handler config")
                self._applied_hooks -= removed_symbols
                with self._lock:
                    for symbol_path in removed_symbols:
                        for hooker in self._get_hookers_for_symbol(symbol_path):
                            if hooker in self._prepared_hookers:
                                self._prepared_hookers.remove(hooker)
                            if hooker in self._applied_hookers:
                                if hooks_enabled:
                                    try:
                                        for h in hooker.hooks:
                                            h.recover()
                                    except Exception as e:
                                        logger.error(f"Failed to recover hooker: {e}")
                                self._applied_hookers.remove(hooker)
                        if symbol_path in self._symbol_to_hooker:
                            del self._symbol_to_hooker[symbol_path]

        self._symbol_handlers_profiling = dict(profiling_handlers)
        self._symbol_handlers_metrics = dict(metrics_handlers)
        self._config_loaded = True
        logger.debug(
            "Loaded handlers for %d symbols (profiling: %d, metrics: %d)",
            len(new_symbol_paths),
            len(self._symbol_handlers_profiling),
            len(self._symbol_handlers_metrics),
        )

    def find_spec(self, fullname, path, target=None):
        """查找模块规范，实现模块导入监听。"""
        if not self._is_target_symbol(fullname):
            return None

        spec = _machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec

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
                self._finder._on_symbol_module_loaded(fullname)

        wrapper = LoaderWrapper()
        wrapper._finder = self
        spec.loader = wrapper
        return spec

    def _is_target_symbol(self, fullname):
        """检查是否是配置中的目标 symbol 模块。"""
        if not self._config_loaded:
            return False
        for symbol_path in self._get_combined_symbol_paths():
            module_path = symbol_path.split(':')[0]
            if fullname == module_path or module_path.startswith(fullname + '.'):
                return True
        return False

    def _on_symbol_module_loaded(self, fullname: str):
        """当 symbol 模块加载完成时的回调。"""
        logger.debug(f"SymbolWatchFinder: Module loaded callback for {fullname}")
        self._prepare_hooks_for_module(fullname)

    def _prepare_hooks_for_module(self, fullname: str):
        """准备模块的 hooks（对 profiling 与 metrics 两路 handler 分别取列表后合并处理）。"""
        module_handlers = []
        for symbol_path in self._get_combined_symbol_paths():
            module_path = symbol_path.split(':')[0]
            if fullname == module_path:
                handler_list = self._get_handlers_for_symbol(symbol_path)
                if handler_list:
                    module_handlers.append((symbol_path, handler_list))
            elif module_path.startswith(fullname + "."):
                try:
                    importlib.import_module(module_path)
                except Exception as e:
                    logger.debug(f"Failed to import {module_path}: {e}")

        if module_handlers:
            logger.debug(f"Detected symbol module loaded: {fullname}, preparing {len(module_handlers)} handler groups")
            self._prepare_handlers_for_module(fullname, module_handlers)

    def _prepare_handlers_for_module(self, module_name: str, module_handlers: List[Tuple[str, List]]):
        """为特定模块准备 Handler。"""
        try:
            for symbol_path, handler_list in module_handlers:
                if symbol_path in self._applied_hooks:
                    logger.debug(f"Handlers for {symbol_path} already prepared, skipping")
                    continue
                hookers_for_symbol = []
                for handler in handler_list:
                    handler.register()
                    self._prepared_hookers.append(handler)
                    hookers_for_symbol.append(handler)
                    if self._auto_apply_enabled:
                        try:
                            handler.init()
                            with self._lock:
                                if handler not in self._applied_hookers:
                                    self._applied_hookers.append(handler)
                            logger.debug(f"Auto-applied handler for symbol {symbol_path}")
                        except Exception as e:
                            logger.error(f"Failed to auto-apply handler for {symbol_path}: {e}")
                self._symbol_to_hooker[symbol_path] = hookers_for_symbol
                self._applied_hooks.add(symbol_path)
                logger.debug(f"Prepared {len(handler_list)} handler(s) for symbol {symbol_path}")
        except Exception as e:
            logger.error(f"Failed to prepare handlers for module {module_name}: {e}")

    def apply_all_hooks(self):
        """应用所有准备好的 hooks。"""
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

    def check_and_apply_existing_modules(self) -> bool:
        """检查目标模块是否已经被导入，如果是则立即准备 hooks。"""
        logger.debug("Checking for already loaded modules...")
        for symbol_path in self._get_combined_symbol_paths():
            module_path = symbol_path.split(":")[0]
            if module_path in sys.modules and symbol_path not in self._applied_hooks:
                logger.debug(f"Module {module_path} already loaded, preparing handlers")
                self._on_symbol_module_loaded(module_path)
        return True
