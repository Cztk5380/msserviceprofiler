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
Function Context: 函数上下文模块

职责：
- 提供FunctionContext类用于存储函数执行上下文

使用示例：
    ctx = FunctionContext()
    ctx.local_values = locals()
    ctx.return_value = result
"""

from typing import Any, Dict, Optional


class FunctionContext:
    """函数执行上下文
    
    用于在hook函数之间传递函数执行状态，包括：
    - local_values: 函数的locals变量
    - return_value: 函数返回值
    
    Attributes:
        local_values: 函数的locals字典
        return_value: 函数返回值
    """
    
    def __init__(self):
        """初始化函数上下文"""
        self._local_values: Optional[Dict[str, Any]] = None
        self.return_value: Any = None
    
    @property
    def local_values(self) -> Optional[Dict[str, Any]]:
        """获取函数的locals字典"""
        return self._local_values
    
    @local_values.setter
    def local_values(self, value: Optional[Dict[str, Any]]):
        """设置函数的locals字典"""
        self._local_values = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """从local_values中获取值
        
        模拟dict的get方法，代理local_values的get操作。
        
        Args:
            key: 变量名
            default: 默认值（当key不存在时返回）
            
        Returns:
            local_values中的值，如果不存在则返回default
        """
        if self._local_values is None:
            return default
        return self._local_values.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """支持通过 ctx['var'] 语法访问local_values"""
        if self._local_values is None:
            raise KeyError(key)
        return self._local_values[key]
    
    def __contains__(self, key: str) -> bool:
        """支持 'var' in ctx 语法检查local_values中是否存在某变量"""
        if self._local_values is None:
            return False
        return key in self._local_values
