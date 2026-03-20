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
Inject: 字节码注入模块

职责：
- 通过字节码注入在函数入口和返回点插入hook代码
- 支持访问函数locals变量
- 支持context manager类型的handler（需要locals的handler）

Context Handler 参数签名：
    - 需要 locals 的 handler: def handler(ctx, local_values): yield

使用示例：
    # 注入函数
    injected_func = inject_function(original_func, context_hook_funcs)
    
    # 使用注入后的函数
    result = injected_func(*args, **kwargs)
"""

import sys
import threading
import types
from typing import Any, Callable, List, Optional

BYTECODE_AVAILABLE = True
try:
    from bytecode import Bytecode, Instr
except ImportError:
    BYTECODE_AVAILABLE = False

from ms_service_metric.utils.logger import get_logger
from ms_service_metric.utils.function_context import FunctionContext

logger = get_logger("inject")

# 最大hook失败次数，超过后跳过该handler
MAX_HOOK_FAILURES = 5


def inject_function(
    ori_func: Callable,
    context_hook_funcs: List[Callable]
) -> Callable:
    """注入函数
    
    通过字节码注入在函数入口和返回点插入hook代码。
    支持访问函数locals变量。
    
    Args:
        ori_func: 原始函数
        context_hook_funcs: 上下文管理器函数列表
            每个函数签名应为: def handler(ctx, local_values): yield
        
    Returns:
        注入后的函数
        
    Raises:
        ImportError: 如果bytecode库不可用
        RuntimeError: 如果注入失败
    """
    if not BYTECODE_AVAILABLE:
        raise ImportError("bytecode library is required for injection")
    
    # Thread-local存储上下文
    thread_local = threading.local()
    thread_local.context = FunctionContext()
    failed_hook_func = [0 for _ in context_hook_funcs]
    
    def get_context() -> FunctionContext:
        """获取当前线程的上下文"""
        if not hasattr(thread_local, "context"):
            thread_local.context = FunctionContext()
        return thread_local.context
    
    def hook_func_when_enter(local_values: dict, *args) -> None:
        """函数入口hook
        
        Args:
            local_values: 函数的locals字典
        """
        running_index = None
        try:
            ctx = get_context()
            ctx.local_values = local_values
            thread_local.hook_context_funcs = []
            
            # 创建context manager，传入ctx和local_values
            for func in context_hook_funcs:
                thread_local.hook_context_funcs.append(func(ctx))
            
            logger.debug(f"function enter: locals={local_values}")
            
            for running_index, func in enumerate(thread_local.hook_context_funcs):
                if failed_hook_func[running_index] >= MAX_HOOK_FAILURES:
                    continue
                func.__enter__()
        except Exception as e:
            logger.error(f"function enter {ori_func.__name__} failed: {e}")
            if running_index is not None and running_index < len(failed_hook_func):
                failed_hook_func[running_index] += 1
    
    def hook_func_when_return(return_value: Any, local_values: Optional[dict] = None, *args) -> None:
        """函数返回hook
        
        Args:
            return_value: 函数返回值
            local_values: 函数的locals字典（返回时的状态）
        """
        try:
            running_index = None
            logger.debug(f"function return: return_value={return_value}, locals={local_values}")
            context = get_context()
            context.local_values = local_values
            context.return_value = return_value
            
            for reversed_running_index, func in enumerate(reversed(thread_local.hook_context_funcs)):
                running_index = len(thread_local.hook_context_funcs) - 1 - reversed_running_index
                if failed_hook_func[running_index] >= MAX_HOOK_FAILURES:
                    continue
                func.__exit__(None, None, None)
        except Exception as e:
            logger.error(f"function exit {ori_func.__name__} failed: {e}")
            if running_index is not None:
                failed_hook_func[running_index] += 1
    
    # 创建新globals避免修改原始函数
    new_globals = {
        **ori_func.__globals__,
        "locals": locals,
        hook_func_when_return.__name__: hook_func_when_return,
        hook_func_when_enter.__name__: hook_func_when_enter,
    }
    
    # 获取原始字节码
    ori_bc = Bytecode.from_code(ori_func.__code__)
    new_instructions = []
    
    def generate_call_instructions(func_name: str, has_ret_value: bool = True) -> list:
        """生成调用hook函数的指令
        
        Args:
            func_name: 要调用的函数名
            has_ret_value: 是否有返回值
            
        Returns:
            指令列表
        """
        call_instructions = []
        
        if sys.version_info >= (3, 11):
            # Python 3.11+ 使用新的CALL指令格式
            call_instructions.append(Instr('LOAD_GLOBAL', (True, func_name)))
            if has_ret_value:
                call_instructions.append(Instr('COPY', 3))  # 将返回值拷贝到栈顶
                call_instructions.append(Instr('LOAD_GLOBAL', (True, "locals")))
                call_instructions.append(Instr('CALL', 0))
                call_instructions.append(Instr('CALL', 2))
            else:
                call_instructions.append(Instr('LOAD_GLOBAL', (True, "locals")))
                call_instructions.append(Instr('CALL', 0))
                call_instructions.append(Instr('CALL', 1))
            call_instructions.append(Instr('POP_TOP'))  # 将返回值删掉
            
        elif sys.version_info >= (3, 8):
            # Python 3.8-3.10
            if has_ret_value:
                call_instructions.append(Instr('DUP_TOP'))
                call_instructions.append(Instr('LOAD_GLOBAL', func_name))
                call_instructions.append(Instr('ROT_TWO'))  # 复制返回值
                call_instructions.append(Instr('LOAD_GLOBAL', "locals"))
                call_instructions.append(Instr('CALL_FUNCTION', 0))
                call_instructions.append(Instr('CALL_FUNCTION', 2))
                call_instructions.append(Instr('POP_TOP'))
            else:
                call_instructions.append(Instr('LOAD_GLOBAL', func_name))
                call_instructions.append(Instr('LOAD_GLOBAL', "locals"))
                call_instructions.append(Instr('CALL_FUNCTION', 0))
                call_instructions.append(Instr('CALL_FUNCTION', 1))
                call_instructions.append(Instr('POP_TOP'))
        else:
            raise RuntimeError(f"Unsupported Python version: {sys.version_info}")
            
        return call_instructions
    
    # 遍历原始字节码，插入hook调用
    found_resume = False
    for item in ori_bc:
        if isinstance(item, Instr) and item.name == 'RETURN_VALUE':
            # 在RETURN_VALUE前插入返回hook
            new_instructions.extend(generate_call_instructions(hook_func_when_return.__name__))
        new_instructions.append(item)
        
        if isinstance(item, Instr) and item.name == 'RESUME' and item.arg == 0:
            # 在函数入口插入hook（Python 3.11+）
            new_instructions.extend(generate_call_instructions(hook_func_when_enter.__name__, False))
            found_resume = True
    
    # Python 3.8-3.10没有RESUME指令，在开头插入hook
    if not found_resume:
        new_instructions = generate_call_instructions(hook_func_when_enter.__name__, False) + new_instructions
    
    # 构建新字节码
    ori_bc.clear()
    ori_bc.extend(new_instructions)
    
    # 生成新代码对象
    new_code = ori_bc.to_code(
        compute_exception_stack_depths=False,
        stacksize=ori_func.__code__.co_stacksize + 2
    )
    
    # 创建新函数
    return types.FunctionType(
        new_code,
        new_globals,
        ori_func.__name__,
        ori_func.__defaults__,
        ori_func.__closure__
    )
