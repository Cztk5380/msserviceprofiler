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
from utils import change_dict
from executor.exec_command import CommandExecutor


class ExecMindIEServer(CommandExecutor):
    def __init__(self, workspace_path):
        super().__init__()
        self.index = str(uuid.uuid4())
        self.mindie_path = "/usr/local/lib/python3.11/site-packages/mindie_llm/"
        self.service_config_path_ori = "conf/config.json"
        self.service_config_path = os.path.join(workspace_path, f"service_config.json")
        self.server_config_change_list = [
            (("ServerConfig", "httpsEnabled"), False),
            (("ServerConfig", "interCommTLSEnabled"), False),
            (("BackendConfig", "interNodeTLSEnabled"), False),
        ]
        self.set_model_path("/model")
        
        self.prof_config_path = os.path.join(workspace_path, f"prof_config.json")
        self.prof_config = {}
        self.set_prof_config(enable=0)

    def set_model_path(self, model_path):
        self.set_server_config(
            "BackendConfig", "ModelDeployConfig", "ModelConfig", 0, "modelWeightPath", value=model_path
        )

    def set_device_id(self, *device_id):
        self.set_server_config("BackendConfig", "npuDeviceIds", value=[[*device_id]])
        self.set_server_config(
            "BackendConfig", "ModelDeployConfig", "ModelConfig", 0, "worldSize", value=len(device_id)
        )

    def set_server_config(self, *key, value=None):
        self.server_config_change_list.append((key, value))

    def set_prof_config(self, **kwargs):
        for key, value in kwargs.items():
            change_dict(self.prof_config, key, value=value)

        self._json_dump(self.prof_config, self.prof_config_path)

    def set_mindie_path(self, mindie_path):
        self.mindie_path = mindie_path

    def ready_go(self):
        # 服务化配置
        with open(file=os.path.join(self.mindie_path, self.service_config_path_ori)) as f:
            service_config = json.load(f)

        for keys, value in self.server_config_change_list:
            change_dict(service_config, *keys, value=value)

        self._json_dump(service_config, self.service_config_path)
        # 老版本MindIE的不支持指定config文件，直接将原本的config.json文件也改掉得了
        self._json_dump(service_config, os.path.join(self.mindie_path, self.service_config_path_ori))

        # 执行
        daemon_file = os.path.join(self.mindie_path, "bin", "mindieservice_daemon")

        self.execute(
            [daemon_file, "--config-file", self.service_config_path], 
            dict(SERVICE_PROF_CONFIG_PATH=self.prof_config_path, 
                MINDIE_LOG_TO_STDOUT='1', 
                MINDIE_LLM_LOG_TO_STDOUT='1'))

        exit_code, has_output = self.wait("Daemon start success!", timeout=600) # 等个10分钟，10分钟都起不来，怕不是卡死了

        print("wait result: ", exit_code, has_output)
        if exit_code is None and has_output == 0:
            return True
        else:
            return False
        
    def _json_dump(self, obj, dump_path):
        with open(file=dump_path, mode="wt") as f:
            json.dump(obj, f, indent=4)

        os.chmod(dump_path, 0o640)


