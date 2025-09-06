# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.checker.npu_cpu_checker import check_npu_cpu
from test.st.checker.dump_checker import mindie_key_word_checker


def test_npu_cpu_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=os.path.join(workspace_path, "prof_data"))
        mindie_server.set_prof_config(enable=1, host_system_usage_freq=1, npu_memory_usage_freq=1)
        assert mindie_server.ready_go()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        benchmark.set_model_path(model_path)
        benchmark.set_dataset_path(dataset_path)
        assert benchmark.curl_test()

        mindie_server.set_prof_config(acl_task_time=0, enable=0)
        mindie_server.kill()

        mindie_key_word_checker(os.path.join(workspace_path, "prof_data"))

        # 开始校验
        check_npu_cpu(os.path.join(workspace_path, "prof_data"))
    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
