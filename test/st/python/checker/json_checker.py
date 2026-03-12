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

import json


def validate_json_keys(file_path: str) -> bool:
    """
    校验JSON文件的键是否符合预期
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        bool: 校验是否通过
    """
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 预期的键集合
    expected_keys = {
        "enable", "prof_dir", "profiler_level", "acl_task_time",
        "acl_prof_task_time_level", "timelimit", "domain"
    }
    
    # 获取实际键集合
    actual_keys = set(data.keys())
    
    # 检查键是否完全匹配
    if actual_keys == expected_keys:
        return True
    else:
        missing_keys = expected_keys - actual_keys
        extra_keys = actual_keys - expected_keys
        
        if missing_keys:
            print(f"  缺少的键: {missing_keys}")
        if extra_keys:
            print(f"  多余的键: {extra_keys}")
        
        return False