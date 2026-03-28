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

import uuid
import os
import json
import time
from utils import change_dict
from executor.exec_command import CommandExecutor
SERVER_STARTUP_TIMEOUT_SECONDS = 600
WAIT_AFTER_CONFIG_CHANGE_SECONDS = 10


class ExecVLLMServer(CommandExecutor):
    def __init__(self, model_path=None, prof_config_path=None):
        super().__init__()
        self.model_path = model_path or "/data/Qwen2.5-0.5B-Instruct"
        self.prof_config_path = prof_config_path or os.environ.get("SERVICE_PROF_CONFIG_PATH", "")


    def ready_go(self):
        self.execute(["vllm", "serve", self.model_path])

        exit_code, has_output = self.wait("Application startup complete.", timeout=SERVER_STARTUP_TIMEOUT_SECONDS) # 等个10分钟，10分钟都起不来，怕不是卡死了

        print("wait result: ", exit_code, has_output)
        if exit_code is None and has_output == 0:
            return True
        else:
            return False


    def change_vllm_profiler_config(self):
        with open(self.prof_config_path, 'r') as f:
            config = json.load(f)
        # 修改enable字段为1
        config['enable'] = 1

        # 写回文件
        with open(self.prof_config_path, 'w') as f:
            json.dump(config, f, indent=4)
        time.sleep(WAIT_AFTER_CONFIG_CHANGE_SECONDS)
