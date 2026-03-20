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
MetaState - 进程元数据状态管理

提供每个进程独立的元数据存储，用于在metrics中提供额外的标签信息。
支持动态更新和获取，供handlers使用。

使用示例:
    >>> from ms_service_metric.core.meta_state import get_meta_state
    >>> meta = get_meta_state()
    >>> meta.set("dp_rank", 0)
    >>> meta.set("model_name", "gpt-4")
    >>> 
    >>> # 在handler中获取
    >>> dp_rank = meta.get("dp_rank", -1)
    >>> model_name = meta.get("model_name", "unknown")
"""

import threading
from typing import Any, Dict, Optional

from ms_service_metric.utils.logger import get_logger

logger = get_logger("meta_state")


class MetaState:
    """进程元数据状态类
    
    每个进程有独立的MetaState实例，存储该进程的元数据信息。
    支持动态更新和获取，线程安全。
    
    Attributes:
        _data: 存储元数据的字典
        _lock: 线程锁
    """
    
    def __init__(self):
        """初始化MetaState"""
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()
        logger.debug("MetaState initialized")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取元数据值
        
        注意：此方法不加锁，允许读取到旧数据，以获得更好的性能。
        Python GIL 保证 dict.get() 操作的原子性。
        
        Args:
            key: 元数据键
            default: 默认值，如果键不存在则返回此值
            
        Returns:
            元数据值或默认值
        """
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置元数据值
        
        Args:
            key: 元数据键
            value: 元数据值
        """
        with self._lock:
            old_value = self._data.get(key)
            self._data[key] = value
            
        if old_value != value:
            logger.debug(f"MetaState updated: {key} = {value} (was {old_value})")
    
    def update(self, data: Dict[str, Any]):
        """批量更新元数据
        
        Args:
            data: 要更新的键值对字典
        """
        with self._lock:
            self._data.update(data)
        
        logger.debug(f"MetaState batch updated: {list(data.keys())}")
    
    def remove(self, key: str) -> bool:
        """删除元数据
        
        Args:
            key: 要删除的键
            
        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                logger.debug(f"MetaState removed: {key}")
                return True
            return False
    
    def clear(self):
        """清空所有元数据"""
        with self._lock:
            self._data.clear()
        logger.debug("MetaState cleared")
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有元数据
        
        Returns:
            元数据字典的副本
        """
        with self._lock:
            return self._data.copy()
    
    def has(self, key: str) -> bool:
        """检查是否存在某个键
        
        Args:
            key: 要检查的键
            
        Returns:
            是否存在
        """
        with self._lock:
            return key in self._data
    
    @property
    def dp_rank(self) -> int:
        """获取数据并行rank（便捷属性）
        
        Returns:
            dp_rank，如果未设置则返回-1
        """
        return self.get("dp_rank", -1)
    
    @dp_rank.setter
    def dp_rank(self, value: int):
        """设置数据并行rank"""
        self.set("dp_rank", value)
    
    @property
    def model_name(self) -> str:
        """获取模型名称（便捷属性）
        
        Returns:
            模型名称，如果未设置则返回"unknown"
        """
        return self.get("model_name", "unknown")
    
    @model_name.setter
    def model_name(self, value: str):
        """设置模型名称"""
        self.set("model_name", value)


# 全局MetaState实例（每个进程独立）
_meta_state_instance: Optional[MetaState] = MetaState()
_meta_state_lock = threading.Lock()


def get_meta_state() -> MetaState:
    """获取全局MetaState实例（单例模式）
    
    每个进程有独立的MetaState实例。
    
    Returns:
        MetaState单例实例
    """
    global _meta_state_instance
    
    if _meta_state_instance is None:
        with _meta_state_lock:
            if _meta_state_instance is None:
                _meta_state_instance = MetaState()
                logger.debug("Created global MetaState instance")
    
    return _meta_state_instance


def reset_meta_state():
    """重置全局MetaState实例
    
    主要用于测试场景。
    """
    global _meta_state_instance
    
    with _meta_state_lock:
        if _meta_state_instance is not None:
            _meta_state_instance.clear()
            _meta_state_instance = None
            logger.debug("Reset global MetaState instance")


# 便捷函数
def get_dp_rank() -> int:
    """获取当前进程的dp_rank
    
    Returns:
        dp_rank，如果未设置则返回-1
    """
    return get_meta_state().dp_rank


def set_dp_rank(rank: int):
    """设置当前进程的dp_rank
    
    Args:
        rank: dp_rank值
    """
    get_meta_state().dp_rank = rank


def get_model_name() -> str:
    """获取当前进程的模型名称
    
    Returns:
        模型名称，如果未设置则返回"unknown"
    """
    return get_meta_state().model_name


def set_model_name(name: str):
    """设置当前进程的模型名称
    
    Args:
        name: 模型名称
    """
    get_meta_state().model_name = name
