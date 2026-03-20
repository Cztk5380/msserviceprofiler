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
HookHelper: Hook辅助类

职责：
- 负责具体的函数替换和恢复
- 保存原始函数，支持恢复

使用示例：
    helper = HookHelper(target_func, hook_func)
    helper.replace()  # 应用hook
    helper.recover()  # 恢复原始函数
"""

import importlib
import types
from typing import Any, Callable, Optional

from ms_service_metric.utils.exceptions import HookError
from ms_service_metric.utils.logger import get_logger

logger = get_logger("hook_helper")


class HookHelper:
    """Hook辅助类
    
    负责具体的函数替换和恢复操作。
    只负责简单的函数替换，复杂的handler合并逻辑由Symbol类处理。
    
    Attributes:
        target: 目标对象（函数或方法）
        hook_func: hook函数
        original_func: 原始函数（用于恢复）
    """
    
    def __init__(self, target: Any, hook_func: Callable):
        """
        初始化HookHelper
        
        Args:
            target: 目标对象（函数、方法或类属性）
            hook_func: hook函数，接收(ori_func, *args, **kwargs)参数
        """
        self._target = target
        self._hook_func = hook_func
        self._original_func: Optional[Callable] = None
        self._replaced = False
        
        # 解析目标对象
        self._target_obj, self._target_name = self._parse_target(target)
        
        logger.debug(f"HookHelper created: target={self._target_name}")
        
    def _parse_target(self, target: Any) -> tuple:
        """
        解析目标对象
        
        确定目标对象所在的容器和属性名。
        
        Args:
            target: 目标对象
            
        Returns:
            (容器对象, 属性名)
        """
        logger.debug(f"Parsing target: {target}")
        # 如果是函数或方法
        if isinstance(target, (types.FunctionType, types.MethodType)):
            # 获取函数所在的模块或类
            if hasattr(target, '__self__'):
                # 绑定方法
                return (target.__self__, target.__name__)
            elif hasattr(target, '__qualname__'):
                # 普通函数或未绑定方法
                # 尝试获取模块
                module = importlib.import_module(target.__module__)
                parts = target.__qualname__.split('.')
                
                logger.debug(f"Module: {module}, parts: {parts}")
                
                # 过滤掉 <locals>，它是嵌套函数的标记，不是真正的属性
                parts = [p for p in parts if p != '<locals>']
                
                # 逐级获取父对象
                obj = module
                for part in parts[:-1]:
                    logger.debug(f"Getting attribute: {part} from {obj}")
                    obj = getattr(obj, part)
                    
                return (obj, parts[-1])
            else:
                raise HookError(f"Cannot parse target: {target}")
        else:
            raise HookError(f"Unsupported target type: {type(target)}")
            
    def replace(self):
        """
        应用hook，替换目标函数
        
        保存原始函数，用hook函数直接替换。
        hook_func应该是一个完整的包装函数，不需要再次包装。
        """
        if self._replaced:
            logger.debug("Hook already applied")
            return
            
        try:
            # 获取原始函数
            self._original_func = getattr(self._target_obj, self._target_name)
            
            # 直接替换为hook函数（hook函数应该是一个完整的包装函数）
            setattr(self._target_obj, self._target_name, self._hook_func)
            self._replaced = True
            
            logger.debug(f"Hook applied: {self._target_name}")
            
        except Exception as e:
            logger.error(f"Failed to apply hook: {e}")
            raise HookError(f"Failed to apply hook: {e}") from e
            
    def recover(self):
        """
        恢复原始函数
        
        将目标函数恢复为原始函数。
        """
        if not self._replaced:
            return
            
        if self._original_func:
            try:
                setattr(self._target_obj, self._target_name, self._original_func)
            except Exception as e:
                logger.error(f"Failed to recover hook: {e}")
                raise HookError(f"Failed to recover hook: {e}") from e
            
        logger.debug(f"Hook recovered: {self._target_name}")
        self._replaced = False
        self._original_func = None
            
    @property
    def is_replaced(self) -> bool:
        """是否已经应用hook"""
        return self._replaced
        
    @property
    def original_func(self) -> Optional[Callable]:
        """原始函数"""
        return self._original_func
