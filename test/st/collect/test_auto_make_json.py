# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.checker.dump_checker import mindie_key_word_checker
from test.st.checker.json_checker import validate_json_keys


def simplified_ready_go(self):
    daemon_file = os.path.join(self.mindie_path, "bin", "mindieservice_daemon")

    self.execute(
        [daemon_file],
        dict(MINDIE_LOG_TO_STDOUT='1',
            MINDIE_LLM_LOG_TO_STDOUT='1'))

    exit_code, has_output = self.wait("Daemon start success!", timeout=600) # 等个10分钟，10分钟都起不来，怕不是卡死了

    print("wait result: ", exit_code, has_output)


def test_auto_make_json_file(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    '''
    测试如果没有配置，会自动生成json文件
    校验内容包括：
        1、校验自动生成了json 文件
        2、校验自动生成json 内容
    '''
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)

        if hasattr(mindie_server, 'prof_config_path') and os.path.exists(mindie_server.prof_config_path):
            os.remove(mindie_server.prof_config_path)
        os.environ['SERVICE_PROF_CONFIG_PATH'] = os.path.join(tmp_workspace, "enable.json")
        
        mindie_server.ready_go = simplified_ready_go.__get__(mindie_server, ExecMindIEServer)
        mindie_server.ready_go()

        mindie_server.kill()
        service_config_path = os.path.join(tmp_workspace, "enable.json")
        file_exists = os.path.exists(service_config_path)

        assert file_exists
        assert validate_json_keys(service_config_path)


    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)