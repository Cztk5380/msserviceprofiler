import types
from bytecode import Bytecode, Instr
import sys
import threading
from .utils import FunctionContext
from .logger import logger

MAX_HOOK_FAILURES = 5

def inject_function(ori_func, context_hook_funcs):
    thread_local = threading.local()
    thread_local.context = FunctionContext()
    failed_hook_func = [0 for x in context_hook_funcs]
    
    def get_context():
        if not hasattr(thread_local, "context"):
            thread_local.context = FunctionContext()
        return thread_local.context
    
    def hook_func_when_enter(local_values, *args):
        try:
            ctx = get_context()
            thread_local.hook_context_funcs = []
            for func in context_hook_funcs:
                thread_local.hook_context_funcs.append(func(ctx))

            running_index = None
            logger.debug(f"function enter: , locals={local_values}")
            ctx.local_values = local_values
            for running_index, func in enumerate(thread_local.hook_context_funcs):
                if failed_hook_func[running_index] >= MAX_HOOK_FAILURES:
                    continue
                func.__enter__()
        except Exception as e:
            logger.error(f"function enter {ori_func.__name__} failed: {e}")
            if running_index is not None:
                failed_hook_func[running_index] += 1
    def hook_func_when_return(return_value, local_values=None, *args):
        try:
            running_index = None
            logger.debug(f"function return: called with return_value={return_value}, locals={local_values}")
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

    # 创建新 globals 避免修改原始函数
    new_globals = {
        **ori_func.__globals__,
        "locals": locals,
        hook_func_when_return.__name__: hook_func_when_return,
        hook_func_when_enter.__name__: hook_func_when_enter,
    }
    ori_bc = Bytecode.from_code(ori_func.__code__)

    new_instructions = []

    def generate_call_instructions(func_name, has_ret_value=True):
        call_instructions = []
        if sys.version_info >= (3, 11):
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
            print("ERROR, unsupport version")
        return call_instructions

    found_resume = False
    for item in ori_bc:
        if isinstance(item, Instr) and item.name == 'RETURN_VALUE':
            new_instructions.extend(generate_call_instructions(hook_func_when_return.__name__))
        new_instructions.append(item)
        if isinstance(item, Instr) and item.name == 'RESUME' and item.arg == 0:
            new_instructions.extend(generate_call_instructions(hook_func_when_enter.__name__, False))
            found_resume = True
    
    if not found_resume:
        new_instructions = generate_call_instructions(hook_func_when_enter.__name__, False) + new_instructions

    ori_bc.clear()
    ori_bc.extend(new_instructions)
    new_code = ori_bc.to_code(compute_exception_stack_depths=False, stacksize=ori_func.__code__.co_stacksize + 2)

    return types.FunctionType(new_code, new_globals, ori_func.__name__, ori_func.__defaults__, ori_func.__closure__)
