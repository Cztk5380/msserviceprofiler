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

from executor.exec_command import CommandExecutor


class ExecBenchmark(CommandExecutor):
    def __init__(self):
        super().__init__()
        self.model_name = "llama"
        self.model_path = "/model"
        self.dataset_path = "/dataset"
        self.server_port = 1025
        self.server_ip = "127.0.0.1"
        self.server_mannager_port = 1026
        self.server_mannager_ip = "127.0.0.1"

    def set_model_path(self, model_path, model_name="llama"):
        self.model_name = model_name
        self.model_path = model_path

    def set_dataset_path(self, dataset_path, dataset_type="gsm8k"):
        self.dataset_type = dataset_type
        self.dataset_path = dataset_path

    def set_service_port(self, server_port, server_ip="127.0.0.1"):
        self.server_port = server_port
        self.server_ip = server_ip

    def set_service_mannager_port(self, server_mannager_port, server_mannager_ip="127.0.0.1"):
        self.server_mannager_port = server_mannager_port
        self.server_mannager_ip = server_mannager_ip

    def curl_test(self):
        # 执行
        self.execute(
            ["curl", f"http://{self.server_ip}:{self.server_port}",
             "-X", "POST",
             "-d", '{"inputs":"Please introduce yourself.","parameters":{"max_new_tokens":250, "temperature":0.3, "top_p":0.3, "top_k":5, "do_sample":true, "repetition_penalty":1.05, "seed":128}}'
             ])

        exit_code, _ = self.wait()
        return exit_code == 0

    def ready_go(self, wait_for=None):
        # 执行
        self.execute(
            ["benchmark",
             "--DatasetPath", self.dataset_path,
             "--DatasetType", self.dataset_type,
             "--ModelName", self.model_name,
             "--ModelPath", self.model_path,
             "--TestType", "client",
             "--Http", f"http://{self.server_ip}:{self.server_port}",
             "--ManagementHttp", f"http://{self.server_mannager_ip}:{self.server_mannager_port}",
             "--Concurrency", 200,
             "--RequestRate", 10,
             "--MaxOutputLen", 128,
             "--Tokenizer", True],
            dict(MINDIE_LOG_TO_STDOUT="benchmark:1; client:1"))

        exit_code, _ = self.wait(target=wait_for)
        print("wait result: ", exit_code)
        return exit_code == 0
