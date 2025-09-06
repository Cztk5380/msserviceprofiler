import os
import uuid

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.executor.exec_parse import ExecParse
from pytest_check import check
from test.st.checker.csv_checker import check_req_csv, check_batch_csv, check_kvcache_csv
from test.st.checker.table_checker import db_connect, check_latency_tables, check_kvcache_table
from test.st.checker.table_checker import check_insight_tables, check_req_status_table
from test.st.checker.trace_checker import check_chrome_tracing
from test.st.checker.dump_checker import mindie_key_word_checker


def test_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=os.path.join(workspace_path, "prof_data"))
        mindie_server.set_prof_config(enable=1, time_limit=18)
        assert mindie_server.ready_go()

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)