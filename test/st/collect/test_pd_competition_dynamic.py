import os
import uuid
import pytest

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.executor.exec_parse import ExecParse
from pytest_check import check
from test.st.checker.csv_checker import check_req_csv, check_batch_csv, check_kvcache_csv
from test.st.checker.table_checker import db_connect, check_latency_tables, check_kvcache_table
from test.st.checker.table_checker import check_insight_tables, check_req_status_table
from test.st.checker.trace_checker import check_chrome_tracing
from test.st.checker.dump_checker import mindie_key_word_checker


def test_dynamic_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
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

        with db_connect(os.path.join(workspace_path, "prof_data_out", "profiler.db")) as conn:
            check_kvcache_table(conn)
            check_insight_tables(conn)
    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
