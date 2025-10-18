# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import os
from pathlib import Path
from pytest_check import check

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.checker.domain_checker import check_db_domain
from test.st.checker.dump_checker import mindie_key_word_checker


def has_prof_folder(root_folder):
    root_path = Path(root_folder)
    for p in root_path.rglob("*"):
        if p.is_dir() and p.name.startswith("PROF_"):
            return True
    return False

def test_domain_acl_prof_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace
        prof_path = os.path.join(workspace_path, "prof_data")

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=prof_path)
        mindie_server.set_prof_config(acl_task_time=1, enable=1, domain="ModelExecute")
        assert mindie_server.ready_go()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        benchmark.set_model_path(model_path)
        benchmark.set_dataset_path(dataset_path)
        assert benchmark.curl_test()

        mindie_server.set_prof_config(acl_task_time=0, enable=0)
        mindie_server.kill()

        # 开始校验
        check.is_true(has_prof_folder(prof_path), f"operator prof data not found in {prof_path}")

        mindie_key_word_checker(prof_path)

        check_db_domain(prof_path,"ModelExecute")

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
