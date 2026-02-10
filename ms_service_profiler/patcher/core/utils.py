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

import os
import threading
from typing import Optional, Dict, Any, List
from .logger import logger


def check_profiling_enabled() -> bool:
    """检查是否启用了性能分析。
    
    通过检查环境变量 SERVICE_PROF_CONFIG_PATH 来判断。
    
    Returns:
        bool: 如果启用了性能分析则返回True，否则返回False
    """
    if not os.environ.get('SERVICE_PROF_CONFIG_PATH'):
        logger.debug("SERVICE_PROF_CONFIG_PATH not set, skipping hooks")
        return False
    return True


def load_yaml_config(config_path: str) -> Optional[List[Dict[str, Any]]]:
    """加载 YAML 配置文件。
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        Optional[List[Dict[str, Any]]]: 配置数据列表，失败时返回 None
        
    Raises:
        ImportError: 当 PyYAML 未安装时
        FileNotFoundError: 当配置文件不存在时
    """
    try:
        import yaml
    except ImportError:
        logger.error("PyYAML is required for configuration loading")
        return None
        
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if config is None:
                return None
            if isinstance(config, list):
                return config
            logger.warning("Configuration file should be a list of hook configurations")
            return []
    except FileNotFoundError:
        logger.warning(f"Configuration file does not exist: {config_path}")
        return None
    except Exception as e:
        logger.error(f"Failed to load YAML configuration: {e}")
        return None


def parse_version_tuple(version_str: str) -> tuple:
    """解析版本字符串为元组。
    
    将版本字符串解析为 (major, minor, patch) 格式的元组。
    处理包含 "+" 或 "-" 的版本字符串，只取主要版本号部分。
    
    Args:
        version_str: 版本字符串，如 "1.2.3+dev" 或 "0.9.2"
        
    Returns:
        tuple: (major, minor, patch) 版本元组
        
    Example:
        >>> parse_version_tuple("1.2.3+dev")
        (1, 2, 3)
        >>> parse_version_tuple("0.9")
        (0, 9, 0)
    """
    if not isinstance(version_str, str):
        return (0, 0, 0)
    parts = version_str.split("+")[0].split("-")[0].split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            break
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


class SharedHookState:
    """共享的 hook 状态类。"""

    def __init__(self):
        """初始化 SharedHookState。"""
        self.request_id_to_prompt_token_len: Dict[str, int] = {}
        self.request_id_to_iter: Dict[str, int] = {}
        self._lock = threading.RLock()  # 添加锁保证线程安全


# 全局单例实例
_GLOBAL_SHARED_STATE = None
_GLOBAL_STATE_LOCK = threading.Lock()


def get_shared_state() -> SharedHookState:
    """获取全局共享的 SharedHookState 实例（线程安全）。"""
    global _GLOBAL_SHARED_STATE

    if _GLOBAL_SHARED_STATE is None:
        with _GLOBAL_STATE_LOCK:
            if _GLOBAL_SHARED_STATE is None:  # 双重检查锁定
                _GLOBAL_SHARED_STATE = SharedHookState()

    return _GLOBAL_SHARED_STATE