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
import json
import shutil
import subprocess
import time
import warnings
from executor.exec_command import CommandExecutor
from utils import change_dict, detect_free_npu_card


class ExecSGLangServer(CommandExecutor):
    """SGLang 服务执行器，用于 ST 场景下启动带 ms_service_profiler 的 SGLang 推理服务"""

    def __init__(self, workspace_path):
        super().__init__()
        self.workspace_path = workspace_path
        self.model_path = "/data/Qwen2.5-0.5B-Instruct"
        self.port = 7399
        self.prof_config_path = os.path.join(workspace_path, "ms_service_profiler_config.json")
        self.prof_config = {}
        self.set_prof_config(enable=0, prof_dir=os.path.join(workspace_path, "prof_data"))

    def set_model_path(self, model_path):
        self.model_path = model_path

    def set_port(self, port):
        self.port = port

    def set_prof_config(self, **kwargs):
        for key, value in kwargs.items():
            change_dict(self.prof_config, key, value=value)
        self._json_dump(self.prof_config, self.prof_config_path)

    def _json_dump(self, obj, dump_path):
        with open(file=dump_path, mode="wt") as f:
            json.dump(obj, f, indent=4)
        os.chmod(dump_path, 0o640)

    def curl_test(self):
        """使用 SGLang OpenAI 兼容的 /v1/completions 接口发送测试请求。使用 subprocess.run 避免 execute() 触发 _reset() 终止 SGLang 进程"""
        curl_body = json.dumps({
            "model": self.model_path,
            "prompt": "Beijing is a",
            "max_tokens": 5,
            "temperature": 0,
        })
        for attempt in range(5):
            result = subprocess.run(
                [
                    "curl", f"http://127.0.0.1:{self.port}/v1/completions",
                    "-H", "Content-Type: application/json",
                    "-X", "POST",
                    "-d", curl_body,
                ],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0:
                return True
            if attempt < 4:
                time.sleep(2)
        return False

    def ready_go(self):
        """启动 SGLang 服务，支持卡失败时换卡重试"""
        self.set_prof_config(enable=1)
        base_env = {
            "SERVICE_PROF_CONFIG_PATH": os.path.abspath(self.prof_config_path),
        }
        cmd = [
            "python", "-m", "sglang.launch_server",
            "--model-path", self.model_path,
            "--device", "npu",
            "--mem-fraction-static", "0.8",
            "--port", str(self.port)
        ]
        card_list = detect_free_npu_card()
        if not card_list:
            print(
                "[WARN] detect_free_npu_card 失败，未配置 ASCEND_RT_VISIBLE_DEVICES，"
                "运行时可能使用默认设备 0，多人并发时易发生显存冲突"
            )
            warnings.warn(
                "detect_free_npu_card failed, skip ASCEND_RT_VISIBLE_DEVICES config",
                UserWarning,
                stacklevel=2,
            )
            env = base_env.copy()
            self.execute(cmd, env=env)
            exit_code, has_output = self._wait_server_ready()
            return exit_code is None and has_output == 0
        for i, device_id in enumerate(card_list[:2]):  # 最多尝试两张卡
            if i > 0:
                # 换卡重试前清空上次失败时的采集数据，避免 warmup 等残留导致 request 数量不符
                prof_data = os.path.join(self.workspace_path, "prof_data")
                prof_data_out = os.path.join(self.workspace_path, "prof_data_out")
                for d in (prof_data, prof_data_out):
                    if os.path.isdir(d):
                        shutil.rmtree(d, ignore_errors=True)
                os.makedirs(prof_data, exist_ok=True)
            env = base_env.copy()
            env["ASCEND_RT_VISIBLE_DEVICES"] = str(device_id)
            print(f"[INFO] 使用第 {device_id} 张卡 (ASCEND_RT_VISIBLE_DEVICES={device_id})")
            self.execute(cmd, env=env)
            exit_code, has_output = self._wait_server_ready()
            if exit_code is None and has_output == 0:
                return True
            self._reset()
            if i < 1:
                print(f"[WARN] 第 {device_id} 张卡启动失败，尝试下一张卡...")
            else:
                print(f"[WARN] 第 {device_id} 张卡启动失败，已达最大重试次数(2)")
        return False

    def _wait_server_ready(self):
        """等待 SGLang 服务就绪"""
        exit_code, has_output = self.wait("The server is fired up and ready to roll!", timeout=600)
        if exit_code is None and has_output == 0:
            return None, 0
        exit_code, has_output = self.wait("Uvicorn running", timeout=60)
        return exit_code, has_output
