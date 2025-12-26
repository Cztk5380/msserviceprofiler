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
import uuid
import pytest

from executor.exec_benchmark import ExecBenchmark
from executor.exec_mindie_server import ExecMindIEServer
from executor.exec_parse import ExecParse
from pytest_check import check
from checker.csv_checker import check_req_csv, check_batch_csv, check_kvcache_csv, check_forward_csv
from checker.table_checker import db_connect, check_latency_tables, check_kvcache_table
from checker.table_checker import check_insight_tables, check_req_status_table
from checker.trace_checker import check_chrome_tracing
from checker.dump_checker import mindie_key_word_checker


def test_dynamic_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    '''
    测试 动态开启 采集+开启算子采集
    校验内容包括：
        1、解析后最终数据是否正确
    '''
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=os.path.join(workspace_path, "prof_data"))
        mindie_server.set_prof_config(enable=0)
        assert mindie_server.ready_go()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        benchmark.set_model_path(model_path)
        benchmark.set_dataset_path(dataset_path)
        mindie_server.set_prof_config(acl_task_time=1, enable=1)
        assert benchmark.curl_test()
        
        mindie_server.set_prof_config(acl_task_time=0, enable=0)
        mindie_server.kill()

        # 开始解析
        parser = ExecParse()
        parser.set_input_path(os.path.join(workspace_path, "prof_data"))
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out"))
        assert parser.ready_go()

        # 解析完了，开始校验
        check_req_csv(os.path.join(workspace_path, "prof_data_out"))
        check_batch_csv(os.path.join(workspace_path, "prof_data_out"))
        check_kvcache_csv(os.path.join(workspace_path, "prof_data_out"))
        check_forward_csv(os.path.join(workspace_path, "prof_data_out"), card_nums=len(devices))

        with db_connect(os.path.join(workspace_path, "prof_data_out", "profiler.db")) as conn:
            check_kvcache_table(conn)
            check_insight_tables(conn)
    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
