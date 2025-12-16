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
import time


from executor.exec_benchmark import ExecBenchmark
from executor.exec_mindie_server import ExecMindIEServer
from checker.npu_cpu_checker import check_npu_cpu
from checker.dump_checker import mindie_key_word_checker


def test_npu_cpu(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    '''
    测试 npu和 cpu 利用率， 将 host_system_usage_freq 和 npu_memory_usage_freq 开启
    校验内容包括：
        1、Prof 文件夹中是否包含cpu 和npu 利用率的数据
    '''
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
        # 开始校验
        time.sleep(10)
        # 开始校验
        os.system(f'tree {os.path.join(workspace_path, "prof_data")}')
        check_npu_cpu(os.path.join(workspace_path, "prof_data"))
    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)


def test_npu_cpu_with_acl_task_time(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    '''
    测试 npu和 cpu 利用率，在 开启 acl_task_time 的场景下， 将 host_system_usage_freq 和 npu_memory_usage_freq 开启
    校验内容包括：
        1、Prof 文件夹中是否包含cpu 和npu 利用率的数据
    '''
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=os.path.join(workspace_path, "prof_data"))
        mindie_server.set_prof_config(enable=1, acl_task_time=1, host_system_usage_freq=1, npu_memory_usage_freq=1)
        assert mindie_server.ready_go()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        benchmark.set_model_path(model_path)
        benchmark.set_service_port(7025)
        benchmark.set_dataset_path(dataset_path)
        assert benchmark.curl_test()
        mindie_server.set_prof_config(acl_task_time=0, enable=0)
        time.sleep(10)
        # 开始校验
        os.system(f'tree {os.path.join(workspace_path, "prof_data")}')
        check_npu_cpu(os.path.join(workspace_path, "prof_data"))

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
