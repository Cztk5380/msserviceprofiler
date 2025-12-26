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
from pytest_check import check

from executor.exec_benchmark import ExecBenchmark
from executor.exec_mindie_server import ExecMindIEServer
from checker.domain_checker import check_db_domain
from checker.dump_checker import mindie_key_word_checker
from checker.checker_utils import has_prof_folder


def test_domain_acl_prof_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    '''
    测试 domain 过滤功能,这个没必要，删除，使用 test_pd_competition_domain 就可以了
    校验内容包括：
        1、最终数据只包含一个domain
    '''
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

        check_db_domain(prof_path, "ModelExecute")

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
