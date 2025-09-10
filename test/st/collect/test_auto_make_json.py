# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.checker.dump_checker import mindie_key_word_checker


def simplified_ready_go(self):
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


def test_auto_make_json_file(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)

        if hasattr(mindie_server, 'prof_config_path') and os.path.exists(mindie_server.prof_config_path):
            os.remove(mindie_server.prof_config_path)
        
        mindie_server.ready_go = simplified_ready_go.__get__(mindie_server, ExecMindIEServer)
        assert mindie_server.ready_go()

        mindie_server.kill()
        service_config_path = os.path.join(workspace_path, "service_config.json")
        file_exists = os.path.exists(service_config_path)

        print(f"检查路径: {service_config_path}")
        print(f"文件是否存在: {file_exists}")

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
