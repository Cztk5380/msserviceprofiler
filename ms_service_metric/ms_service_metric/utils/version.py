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
版本工具模块

提供获取包版本号的工具函数。
"""

from typing import Optional

from packaging.version import Version
from ms_service_metric.utils.logger import get_logger

logger = get_logger("version")


def get_package_version(package_name: str) -> Optional[str]:
    """获取已安装包的版本号。
    
    优先使用 Python 3.8+ 内置的 importlib.metadata，
    如果失败则尝试从包的 __version__ 属性获取。
    
    Args:
        package_name: 包名，如 "vllm", "sglang"
        
    Returns:
        Optional[str]: 版本号，如果包未安装则返回 None
    """
    # 优先使用 Python 3.8+ 内置的 importlib.metadata
    try:
        from importlib.metadata import version
        return version(package_name)
    except ImportError:
        pass
    except Exception:
        pass
    
    # 如果无法获取，尝试从包的 __version__ 属性获取
    try:
        import importlib
        module = importlib.import_module(package_name)
        return getattr(module, "__version__", None)
    except Exception:
        return None


def check_version_match(current_version: Optional[str], min_version: Optional[str], max_version: Optional[str]) -> bool:
    """检查当前版本是否在指定的版本范围内
    
    使用 packaging.version 进行版本比较，支持语义化版本。
    
    Args:
        current_version: 当前版本，如 "1.2.3"
        min_version: 最小版本要求（包含），如 "1.0.0"
        max_version: 最大版本要求（包含），如 "2.0.0"
        
    Returns:
        如果版本在范围内返回True，否则返回False
    """
    # 如果没有版本限制，直接返回 True
    if not min_version and not max_version:
        return True
    
    # 如果没有当前版本，但有版本限制，返回 False
    if not current_version:
        logger.warning(f"No version found for package")
        return False
    
    current = Version(current_version)
    
    if min_version:
        if current < Version(min_version):
            return False
    
    if max_version:
        if current > Version(max_version):
            return False
    
    return True
