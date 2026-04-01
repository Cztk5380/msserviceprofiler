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
"""Hook 链管理系统

实现双向链表管理多个 hook 函数，支持动态添加、删除和调用。
对外接口：
1. add_hook(ori_func, hook_func) -> HookNode
2. HookNode.remove() -> bool
3. HookNode.call_prev(*args, **kwargs) -> 调用上一个
"""

import logging
import threading
from enum import Enum
from typing import Any, Callable, Optional, Set

logger = logging.getLogger(__name__)


class _NoResult(Enum):
    """用于表示还没有结果的特殊枚举值"""
    NO_RESULT = object()


NO_RESULT = _NoResult.NO_RESULT


class HookNode:
    """Hook 链表节点"""
    
    def __init__(self, chain: 'HookChain', prev_node: Optional['HookNode'] = None):
        self.chain = chain
        self.hook_func = self.call_prev
        self.prev_node = prev_node
        self.next_node: Optional['HookNode'] = None
    
    @property
    def ori_wrap(self):
        return self.call_prev
    
    def set_hook_func(self, hook_func: Callable):
        self.hook_func = hook_func
    
    
    def call_prev(self, *args, **kwargs):
        """调用上一个 hook 函数"""
        if self.prev_node:
            return self.prev_node.hook_func(*args, **kwargs)
        else:
            return self.chain._call_ori_func(*args, **kwargs)
    
    def remove(self) -> bool:
        return self.chain.remove_chain_node(self)
    
    def recover(self):
        return self.remove()


class HookChain:
    """Hook 链表管理器"""
    
    def __init__(self, ori_func: Callable):
        self.ori_func = ori_func
        self.head: Optional[HookNode] = None
        self.tail: Optional[HookNode] = None
        self._nodes: Set[HookNode] = set()
        self._lock = threading.Lock()
        self._helper = None
        self._last_result = NO_RESULT  # 保存最后一次调用的结果
        
    def set_last_result(self, result):
        """设置最后一次调用的结果
        
        供外部使用（如字节码注入的场景），用于标记已经获取到结果
        
        Args:
            result: 要保存的结果值
        """
        self._last_result = result
        return result
        
    def _call_ori_func(self, *args, **kwargs):
        """调用原始函数并保存结果
        
        如果 ori_func 抛出异常，将异常包装后保存，并重新抛出
        """
        try:
            result = self.ori_func(*args, **kwargs)
            self._last_result = result
            return result
        except Exception as e:
            # ori_func 抛出异常，保存异常并重新抛出
            self._last_result = e
            raise
        
    def remove_chain_node(self, node: HookNode) -> bool:
        """删除节点"""
        with self._lock:
            if node not in self._nodes:
                return False
            
            if node.prev_node:
                node.prev_node.next_node = node.next_node
            else:
                self.head = node.next_node
            
            if node.next_node:
                node.next_node.prev_node = node.prev_node
            else:
                self.tail = node.prev_node
            
            self._nodes.remove(node)
            
            # 打印删除后的 chain 信息
            self.print_chain_info("Remove")
            
            return True
    
    def replace_chain(self) -> None:
        """对入口函数执行 replace：链非空时确保 HookHelper 存在并替换为 chain closure。"""
        with self._lock:
            if self.tail is None:
                return
            if self._helper is None:
                from ms_service_metric.core.hook.hook_helper import HookHelper
                excute = self.exec_chain_closure()
                setattr(excute, '_hook_chain', self)
                self._helper = HookHelper(self.ori_func, excute)
            helper = self._helper
            if helper.is_replaced:
                return
        try:
            helper.replace()
        except Exception as e:
            logger.error(
                f"Failed to replace hook for {self.ori_func.__name__}: {e}. "
                f"This is an internal error. Please report this issue to "
                f"https://gitcode.com/Ascend/msserviceprofiler/discussions"
            )
            raise
    
    def add_chain_node(self, insert_at_head: bool = False) -> HookNode:
        """添加节点，返回 HookNode

        Args:
            insert_at_head: 如果为 True，插入到链表头部；否则插入到尾部（默认）
        """
        is_empty = False
        with self._lock:
            is_empty = self.tail is None

            if insert_at_head and self.head:
                # 插入到头部
                new_node = HookNode(self, None)
                new_node.next_node = self.head
                self.head.prev_node = new_node
                self.head = new_node
            else:
                # 插入到尾部（默认）
                new_node = HookNode(self, self.tail)
                if self.tail:
                    self.tail.next_node = new_node
                    self.tail = new_node
                else:
                    self.head = self.tail = new_node

            self._nodes.add(new_node)

        # 打印添加后的 chain 信息
        self.print_chain_info("Add")

        # 在锁外执行 replace，避免阻塞其他线程
        if is_empty:
            self.replace_chain()

        return new_node
    
    def get_chain_info(self) -> dict[str, Any]:
        """获取 chain 的调试信息

        Returns:
            包含 chain id、node 列表 id 和数量的字典
        """
        node_ids = [id(node) for node in self._nodes]
        info = {
            "chain_id": id(self),
            "node_count": len(self._nodes),
            "node_ids": node_ids
        }
        return info
    
    def print_chain_info(self, action: str = "Info"):
        """打印 chain 的调试信息
        
        Args:
            action: 操作类型，如 "Add", "Remove", "Info" 等
        """
        info = self.get_chain_info()
        func_name = getattr(self.ori_func, '__name__', str(self.ori_func))
        func_module = getattr(self.ori_func, '__module__', 'unknown')
        func_path = f"{func_module}.{func_name}"
        logger.debug(f"[HookChain {func_path}]  {action}, name={func_name}, chain_id={info['chain_id']}, node_count={info['node_count']}, node_ids={info['node_ids']}")
    
    def exec_chain_closure(self):
        def execute_hook_chain(*args, **kwargs):
            """执行 hook 链，带有异常保护机制
            
            保护策略：
            1. 先将 _last_result 重置为 NO_RESULT
            2. 执行 hook 链
            3. 如果执行过程中发生异常：
            - 如果 _last_result 还是 NO_RESULT（说明还没调用到 ori_func），主动调用一次 ori_func 并返回
            - 如果 _last_result 是异常（说明 ori_func 抛出了异常），直接重新抛出
            - 如果 _last_result 已经有正常值（说明已经调用过 ori_func），直接返回保存的结果
            4. 如果正常执行完成，返回 hook 链的结果
            """
            # 重置结果状态
            self._last_result = NO_RESULT
            
            logger.debug("Executing hook chain for %s", self.ori_func.__name__)
            try:
                if self.tail is None:
                    # 没有 hook 节点，直接调用原函数
                    return self.ori_func(*args, **kwargs)
                else:
                    # 执行 hook 链
                    logger.debug(f"Executing hook chain for {self.ori_func.__name__}")
                    return self.tail.hook_func(*args, **kwargs)
            except Exception as ex:
                logger.error(
                    f"Exception occurred in hook chain for {self.ori_func.__name__}: {ex}. "
                    f"If this issue persists, please report it to: "
                    f"https://gitcode.com/Ascend/msserviceprofiler/discussions"
                )
                logger.debug(f"Hook chain exception details: {ex}", exc_info=True)
                # 发生异常，检查是否已经调用过 ori_func
                if self._last_result is NO_RESULT:
                    # 还没调用到 ori_func，主动调用一次
                    return self.ori_func(*args, **kwargs)
                elif isinstance(self._last_result, Exception):
                    # ori_func 本身抛出了异常，直接重新抛出
                    raise self._last_result
                else:
                    # 已经调用过 ori_func 并返回了正常结果，返回保存的结果
                    return self._last_result
        
        return execute_hook_chain


def get_chain(ori_func: Callable) -> HookChain:
    """获取或创建 HookChain（公共函数）"""
    with _cache_lock:
        if hasattr(ori_func, '_hook_chain') and getattr(ori_func, '_hook_chain') is not None:
            return getattr(ori_func, '_hook_chain')

        chain = HookChain(ori_func)

        try:
            setattr(ori_func, '_hook_chain', chain)
        except AttributeError:
            func_name = getattr(ori_func, '__name__', str(ori_func))
            func_module = getattr(ori_func, '__module__', 'unknown')
            logger.warning(
                f"Cannot cache hook chain for {func_module}.{func_name}: "
                f"object does not support attribute assignment. "
                f"Hook chain will be created on each call, which may impact performance."
            )

        return chain


# 全局链缓存
_cache_lock = threading.Lock()
