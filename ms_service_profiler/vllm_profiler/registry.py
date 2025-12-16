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

# 全局注册表存储所有hookers
HOOK_REGISTRY = []
# 仅用于在基于配置的场景下，临时保存已导入的内置 Hooker 列表
BUILTIN_HOOKERS_CACHE = []


def clear_hook_registry():
    """清空全局 hook 注册表。"""
    HOOK_REGISTRY.clear()


def clear_builtin_cache():
    """清空内置 hooker 缓存。"""
    BUILTIN_HOOKERS_CACHE.clear()


def get_hook_registry():
    """获取全局 hook 注册表。
    
    Returns:
        List: hook 注册表列表
    """
    return HOOK_REGISTRY


def get_builtin_cache():
    """获取内置 hooker 缓存。
    
    Returns:
        List: 内置 hooker 缓存列表
    """
    return BUILTIN_HOOKERS_CACHE


def add_to_hook_registry(hooker):
    """添加 hooker 到全局注册表。
    
    Args:
        hooker: 要添加的 hooker 实例
    """
    HOOK_REGISTRY.append(hooker)


def set_builtin_cache(cache):
    """设置内置 hooker 缓存。
    
    Args:
        cache: 要设置的缓存列表
    """
    if cache is None:
        BUILTIN_HOOKERS_CACHE.clear()
        return
    # 就地替换，保持引用不变
    BUILTIN_HOOKERS_CACHE.clear()
    BUILTIN_HOOKERS_CACHE.extend(list(cache))
