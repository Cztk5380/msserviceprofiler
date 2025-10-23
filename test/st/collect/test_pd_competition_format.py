import os
import uuid

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.executor.exec_parse import ExecParse
from pytest_check import check
from test.st.checker.csv_checker import check_req_csv, check_batch_csv, check_kvcache_csv, check_forward_csv
from test.st.checker.table_checker import db_connect, check_latency_tables, check_kvcache_table
from test.st.checker.table_checker import check_insight_tables, check_req_status_table
from test.st.checker.trace_checker import check_chrome_tracing
from test.st.checker.dump_checker import mindie_key_word_checker
from test.st.checker.checker_utils import count_files_with_single_extension


def test_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=os.path.join(workspace_path, "prof_data"))
        mindie_server.set_prof_config(enable=1)
        assert mindie_server.ready_go()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        benchmark.set_model_path(model_path)
        benchmark.set_dataset_path(dataset_path)
        assert benchmark.curl_test()

        mindie_server.set_prof_config(acl_task_time=0, enable=0)
        mindie_server.kill()

        mindie_key_word_checker(os.path.join(workspace_path, "prof_data"))

        # 开始解析
        parser = ExecParse()
        parser.set_input_path(os.path.join(workspace_path, "prof_data"))

        # format设置为csv
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out_csv"))
        parser.add_param('--format', 'csv')
        assert parser.ready_go()
        assert count_files_with_single_extension(os.path.join(workspace_path, "prof_data_out_csv"), '.csv') == 4
        check_req_csv(os.path.join(workspace_path, "prof_data_out_csv"))
        check_batch_csv(os.path.join(workspace_path, "prof_data_out_csv"))
        check_kvcache_csv(os.path.join(workspace_path, "prof_data_out_csv"), complete_req_cnt=1)
        check_forward_csv(os.path.join(workspace_path, "prof_data_out_csv"), card_nums=len(devices))

        # format设置为db
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out_db"))
        parser.add_param('--format', 'db')
        assert parser.ready_go()
        assert count_files_with_single_extension(os.path.join(workspace_path, "prof_data_out_db"), '.db') == 1
        with db_connect(os.path.join(workspace_path, "prof_data_out_db", "profiler.db")) as conn:
            check_latency_tables(conn, complete_req_cnt=1)
            check_kvcache_table(conn, complete_req_cnt=1)
            check_req_status_table(conn, complete_req_cnt=1)
            check_insight_tables(conn, complete_req_cnt=1)

        # format设置为json
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out_json"))
        parser.add_param('--format', 'json')
        assert parser.ready_go()
        assert count_files_with_single_extension(os.path.join(workspace_path, "prof_data_out_json"), '.json') == 1
        check_chrome_tracing(os.path.join(workspace_path, "prof_data_out_json"))
    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
