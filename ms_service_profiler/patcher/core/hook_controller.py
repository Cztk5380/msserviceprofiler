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
Hook 控制器：统一管理 hook 的启用/禁用状态和流程。

职责：
- 状态管理（enabled/disabled）
- 流程控制（enable/disable）
- 协调 SymbolWatchFinder 的操作
- 生成 C++ 回调函数

依赖：
- SymbolWatchFinder（执行层）
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from .logger import logger
from .symbol_watcher import SymbolWatchFinder

GetHandlers = Callable[[], Optional[dict]]


class HookController:
    """Hook 控制器：统一管理 hook 的启用/禁用状态和流程。
    
    该类是 hook 生命周期的唯一控制点，负责：
    - 状态管理：_enabled 是唯一的状态变量
    - 流程控制：协调 SymbolWatchFinder 的 load/prepare/apply/recover
    - 回调生成：提供可注册到 C++ 的回调函数
    
    Attributes:
        _watcher: SymbolWatchFinder 实例（执行层）
        _enabled: hooks 是否已启用
    """
    
    def __init__(self, watcher: SymbolWatchFinder):
        """初始化 HookController。
        
        Args:
            watcher: SymbolWatchFinder 实例
        """
        self._watcher = watcher
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """hooks 是否已启用。"""
        return self._enabled
    
    def enable(
        self,
        profiling_handlers: Optional[dict] = None,
        metrics_handlers: Optional[dict] = None,
    ) -> int:
        """启用 hooks（支持重复调用以动态更新配置）。
        
        每次调用使用传入的 profiling 与 metrics 两路 Handler 字典，支持动态增删点位。
        
        Args:
            profiling_handlers: ConfigLoader.load_profiling() 的解析结果
            metrics_handlers: ConfigLoader.load_metrics() 的解析结果
            
        Returns:
            当前已启用的 hook 数量
        """
        try:
            if self._enabled:
                logger.info("Reloading hook configuration...")
            else:
                logger.info("Enabling profiler hooks...")

            if not profiling_handlers and not metrics_handlers:
                logger.warning("No configuration loaded")
                return 0

            self._watcher.load_handlers(
                profiling_handlers=profiling_handlers,
                metrics_handlers=metrics_handlers,
                hooks_enabled=self._enabled,
            )
            
            # 2. 为已加载的模块准备 hooks
            self._watcher.check_and_apply_existing_modules()
            
            # 3. 应用所有已准备的 hooks
            all_hookers = self._watcher.apply_all_hooks()
            
            # 4. 设置自动应用（后续模块加载时自动 apply）
            self._watcher.set_auto_apply(True)
            
            self._enabled = True
            logger.info(f"Successfully enabled {len(all_hookers)} hooks")
            return len(all_hookers)
            
        except Exception as e:
            logger.exception("Failed to enable hooks: %s", str(e))
            return 0
    
    def disable(self) -> int:
        """禁用所有 hooks（将函数恢复为原函数）。
        
        Returns:
            成功禁用的 hook 数量
        """
        if not self._enabled:
            logger.debug("Hooks not enabled, nothing to disable")
            return 0
        
        try:
            logger.info("Disabling profiler hooks...")
            
            # 1. 停止自动应用
            self._watcher.set_auto_apply(False)
            
            # 2. 恢复所有已应用的 hooks
            hookers = self._watcher.get_applied_hookers()
            total = len(hookers)
            failed = 0
            
            for hooker in hookers:
                try:
                    for hook_helper in getattr(hooker, "hooks", []):
                        hook_helper.recover()
                except Exception as e:
                    logger.error(f"Failed to recover hook {hooker}: {e}")
                    failed += 1
            
            self._enabled = False
            success = total - failed
            logger.info(f"Successfully disabled {success}/{total} hooks")
            return success
            
        except Exception as e:
            logger.exception("Failed to disable hooks: %s", str(e))
            return 0
    
    def get_callbacks(self, get_handlers: GetHandlers) -> Tuple[Callable[[], None], Callable[[], None]]:
        """返回可注册到 C++ 的回调函数对（start, stop）。
        
        Args:
            get_handlers: 可调用对象，返回 (profiling_handlers, metrics_handlers) 或单 dict 兼容；
                on_start 被调用时会先执行 get_handlers() 再将两路结果传给 enable()
        
        Returns:
            (on_start_callback, on_stop_callback)
        """
        def on_start() -> None:
            try:
                logger.info("Received profiler start signal from C++")
                result = get_handlers()
                if isinstance(result, tuple) and len(result) == 2:
                    self.enable(profiling_handlers=result[0], metrics_handlers=result[1])
                else:
                    self.enable(profiling_handlers=result, metrics_handlers=None)
            except Exception as e:
                logger.exception(f"Failed to handle profiler start: {e}")

        def on_stop() -> None:
            try:
                logger.info("Received profiler stop signal from C++")
                self.disable()
            except Exception as e:
                logger.exception(f"Failed to handle profiler stop: {e}")

        return on_start, on_stop
