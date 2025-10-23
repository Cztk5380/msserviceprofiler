import os

from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.executor.exec_parse import ExecParse
from test.st.checker.csv_checker import has_op_statistic_csv, has_op_summary_csv


def test_acl_datatype_config_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
    try:
        workspace_path = tmp_workspace
        prof_path = os.path.join(workspace_path, "prof_data")

        # 启动服务
        mindie_server = ExecMindIEServer(workspace_path)
        mindie_server.set_device_id(*devices)
        mindie_server.set_mindie_path(mindie_path)
        mindie_server.set_model_path(model_path)
        mindie_server.set_prof_config(prof_dir=prof_path)
        mindie_server.set_prof_config(enable=0)
        assert mindie_server.ready_go()

        # curl 一条试试深浅
        benchmark = ExecBenchmark()
        benchmark.set_model_path(model_path)
        benchmark.set_dataset_path(dataset_path)
        mindie_server.set_prof_config(
            acl_task_time=1,
            enable=1,
            aclDataTypeConfig="ACL_PROF_TASK_TIME, ACL_PROF_ACL_API, ACL_PROF_AICORE_METRICS",
            aclprofAicoreMetrics="ACL_AICORE_PIPE_UTILIZATION",
        )
        assert benchmark.curl_test()
        mindie_server.set_prof_config(enable=0)
        mindie_server.kill()

        # 开始解析
        parser = ExecParse()
        parser.set_input_path(prof_path)
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out"))
        assert parser.ready_go()

        # 解析完了，开始校验相关文件的生成
        assert has_op_statistic_csv(os.path.join(workspace_path, "prof_data_out"))
        assert has_op_summary_csv(os.path.join(workspace_path, "prof_data_out"))

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)
