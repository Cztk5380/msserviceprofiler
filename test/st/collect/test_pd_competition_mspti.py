import os

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.executor.exec_parse import ExecParse
from test.st.checker.table_checker import run_ep_balance_sub_test, run_moe_analysis_test


def test_mspti_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=os.path.join(workspace_path, "prof_data"))
        mindie_server.set_prof_config(acl_task_time=2, enable=1)
        assert mindie_server.ready_go()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        benchmark.set_model_path(model_path)
        benchmark.set_dataset_path(dataset_path)
        assert benchmark.curl_test()

        mindie_server.set_prof_config(acl_task_time=0, enable=0)
        mindie_server.kill()

        # 开始解析
        parser = ExecParse()
        parser.set_input_path(os.path.join(workspace_path, "prof_data"))
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out"))
        assert parser.ready_go()

        # 新增数据库字段校验子测试
        run_ep_balance_sub_test(os.path.join(workspace_path, "prof_data_out"))
        run_moe_analysis_test(os.path.join(workspace_path, "prof_data_out"))

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)