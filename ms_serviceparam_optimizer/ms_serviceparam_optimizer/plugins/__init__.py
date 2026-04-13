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
from typing import Callable, Dict
from importlib.metadata import entry_points
from loguru import logger

_PLUGINS_LOADED_FLAG = False


def _iter_entry_points(group: str):
    """遍历指定组的入口点，处理不同Python版本的兼容性"""
    eps = entry_points()
    if hasattr(eps, 'select'):
        yield from eps.select(group=group)
    else:
        for ep in eps.get(group, []):
            yield ep


def load_plugins_by_group(group: str) -> Dict[str, Callable]:
    """加载指定组的插件，返回插件名称到可调用对象的映射"""
    plugins = {}
    
    try:
        eps = list(_iter_entry_points(group))
    except Exception as e:
        logger.warning("Failed to retrieve entry points for group '{}': {}", group, e)
        return plugins
    
    if not eps:
        return plugins
    
    logger.info("Loading plugins from group '{}':", group)
    for ep in eps:
        try:
            loaded_func = ep.load()
            plugins[ep.name] = loaded_func
            logger.info("  - {} => {} [OK]", ep.name, ep.value)
        except Exception:
            logger.exception("  - {} => {} [FAILED]", ep.name, ep.value)
    
    return plugins


def load_general_plugins():
    """加载并执行通用插件，确保每个进程只执行一次"""
    global _PLUGINS_LOADED_FLAG
    if _PLUGINS_LOADED_FLAG:
        return None
    _PLUGINS_LOADED_FLAG = True
    
    plugins = load_plugins_by_group(group='ms_serviceparam_optimizer.plugins')
    for name, func in plugins.items():
        try:
            func()
        except Exception:
            logger.exception("Plugin '{}' execution failed", name)
    
    return plugins
