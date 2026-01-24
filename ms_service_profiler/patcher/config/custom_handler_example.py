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

from ..core.logger import logger


def kvcache_manager_free_example_handler(original_func, this, request, *args, **kwargs):
    """
    当前函数为用例介绍，应用的方式在 hooks_example.yaml 中
    可根据自己的需要编写 handler 函数，比如下面的例子就是：
    
    对 KVCacheManager 的 free 函数进行hook，将每一次 free 的 request 的 request_id
    记录到 patcher 的日志中，其中：
    - `original_func` 是原本的函数
    - `this` 是当前 KVCacheManager 的这个对象
    - `request` 是 KVCacheManager.free 的唯一入参
    - `*args` 和 `**kwargs` 根据自己的需要进行传入，有些函数会使用到那这里需要保留
    """
    # 1. 在调用 original_func 之前可以执行一些简单的 preprocess，比如对函数的入参或者当前
    #    对象的一些属性做一些简单的数据处理, 这里省略
    original_func(this, *args, **kwargs)
    # 2. 调用原函数，如果原函数有返回值，记得保存返回值，并在 handler 函数最后将结果返回。
    #    比如 res = original_func(this, *args, **kwargs)
    logger.info(f"KV blocks taken by {request.request_id} is free")
    # 3. 调用原函数之后，可以对函数的返回结果等做一些 postprocess。这里将 request_id 的
    #    kvcache 释放信号通过日志记录了下来
    # 4. 如果原函数有返回值，记得在 handler 函数末尾加上 return res
