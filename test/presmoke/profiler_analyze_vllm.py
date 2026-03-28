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
import shutil
import time
import uuid

from executor.exec_benchmark import ExecBenchmark
from executor.exec_vllm_server import ExecVLLMServer
from executor.exec_parse import ExecParse
from pytest_check import check
from checker.csv_checker import check_req_csv, check_batch_csv, check_kvcache_csv, check_forward_csv
from checker.table_checker import db_connect, check_latency_tables, check_kvcache_table
from checker.table_checker import check_insight_tables, check_req_status_table
from checker.trace_checker import check_chrome_tracing
from checker.dump_checker import mindie_key_word_checker


def test_vllm_profiler_analyze(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    '''
    基础采集测试，不带算子采集
    校验内容包括：
        1、数据是否正常
    '''
    vllm_server = None
    try:
        profiler_output_path = "/root/.ms_server_profiler"
        if os.path.exists(profiler_output_path):
            shutil.rmtree(profiler_output_path)

        # 启动服务
        vllm_server = ExecVLLMServer()
        assert vllm_server.ready_go()

        vllm_server.change_vllm_profiler_config()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        assert benchmark.curl_vllm_test()
        time.sleep(20)

        vllm_server.kill()

        # 开始解析
        parser = ExecParse()
        analyze_output_path = "/root/.ms_server_analyze"
        shutil.rmtree(analyze_output_path, ignore_errors=True)
        parser.set_input_path(profiler_output_path)
        parser.set_output_path(analyze_output_path)
        assert parser.ready_go()

        # 解析完了，开始校验
        check_req_csv(analyze_output_path)
        check_batch_csv(analyze_output_path, framework="vllm")
        check_kvcache_csv(analyze_output_path, complete_req_cnt=1)
        check_forward_csv(analyze_output_path, card_nums=len(devices))

        with db_connect(os.path.join(analyze_output_path, "profiler.db")) as conn:
            check_latency_tables(conn, complete_req_cnt=1, framework="vllm")
            check_kvcache_table(conn, complete_req_cnt=1)
            check_insight_tables(conn, complete_req_cnt=1, framework="vllm")

        check_chrome_tracing(analyze_output_path)

    finally:
        if vllm_server:
            vllm_server.kill()
