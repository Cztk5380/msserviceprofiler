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

from pathlib import Path


def check_npu_cpu(output_path):
    """
    检查 root_dir 下所有 PROF_ 开头的文件夹中：
    - 是否存在包含 'CpuUsage' 的文件
    - 是否存在包含 'Memory'   的文件

    只有都存在才通过
    缺少任一类，assert 失败并提示缺少哪一个
    """
    root = Path(output_path)

    # 断言：根目录必须存在
    assert root.exists(), f"Root directory does not exist: {output_path}"
    assert root.is_dir(), f"Root path is not a directory: {output_path}"

    # 找到所有 PROF_ 开头的文件夹
    prof_folders = [f for f in root.rglob("*") if f.is_dir() and f.name.startswith("PROF_")]

    # 断言：必须有至少一个 PROF_ 文件夹
    assert len(prof_folders) > 0, f"No PROF_ folders found in {output_path}"

    # 收集两类文件
    cpu_files = []
    memory_files = []

    for folder in prof_folders:
        # 递归查找所有文件
        for file in folder.rglob("*"):
            if file.is_file():
                if 'CpuUsage' in file.name:
                    cpu_files.append(file)
                if 'Memory' in file.name:
                    memory_files.append(file)

    # 核心断言：必须两类文件都存在
    missing = []
    if len(cpu_files) == 0:
        missing.append("CpuUsage")
    if len(memory_files) == 0:
        missing.append("Memory")

    # 如果缺少，抛出详细错误
    assert len(missing) == 0, (
        f" 文件校验失败！缺少: {', '.join(missing)}\n"
        f" 搜索路径: {output_path}\n"
        f" PROF_ 文件夹数量: {len(prof_folders)}\n"
        f" CpuUsage 文件数量: {len(cpu_files)}\n"
        f" Memory 文件数量: {len(memory_files)}"
    )

    return True
