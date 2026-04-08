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
import glob
from pathlib import Path
from msguard.security import open_s
from test.st.python.executor.exec_command import CommandExecutor


def check_csv_no_empty_start(csv_file):
    with open_s(csv_file, 'r', encoding='utf-8') as f:
        next(f)  # 跳过标题行（第一行）

        for _, line in enumerate(f, start=2):  # 从第2行开始检查（数据行）
            stripped_line = line.strip()
            
            # 检查是否以逗号开头（即第一个单元格是否为空）
            if stripped_line.startswith(','):
                return False

        return True
    

def test_example():
    '''
    基础采集测试，不带算子采集
    校验内容包括：
        1、数据是否正常
    '''
    workspace_path = Path("/data/optimizer_presmoke")
    try:
        # 切换到workspace_path目录下执行命令
        os.chdir(workspace_path)
        # 设置环境变量
        os.environ["MODEL_EVAL_STATE_CONFIG_PATH"] = "/data/optimizer_presmoke/config.toml"
        cmd = "msserviceprofiler optimizer"
        exec_cmd = CommandExecutor()
        exec_cmd.execute(cmd)
        # 等待命令执行完成，target=None 表示等待进程退出
        exit_code, _ = exec_cmd.wait(target=None)
        assert exit_code == 0, f"msserviceprofiler optimizer 命令执行失败，退出码: {exit_code}"
        pattern = os.path.join(workspace_path, "result", "store", "data_storage_*.csv")
        matched_files = glob.glob(pattern)

        assert len(matched_files) == 1

        csv_file = matched_files[0]  # 取第一个匹配的文件
        result = check_csv_no_empty_start(csv_file)  # 调用检查函数
        assert result is True, "CSV文件中存在空行"
        
    finally:
        result_path = os.path.join(workspace_path, "result")
        if os.path.exists(result_path):
            import shutil
            shutil.rmtree(result_path)