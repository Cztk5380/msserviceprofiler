import json
import os

from test.st.executor.exec_mindie_server import ExecMindIEServer


def test_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=os.path.join(workspace_path, "prof_data"))
        mindie_server.set_prof_config(enable=1, timelimit=18)
        assert mindie_server.ready_go()
        assert mindie_server.wait("Profiler Timelimit 18 Seconds Is Reached, Profiler Disabled Successfully!", 18)
        with open(mindie_server.prof_config_path, "r", encoding="utf-8") as f:
            prof_config = json.load(f)
        assert prof_config["enable"] == 0

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)