import os

from pytest_check import check
from test.st.executor.exec_benchmark import ExecBenchmark
from test.st.executor.exec_mindie_server import ExecMindIEServer
from test.st.checker.dump_checker import grep_in_directory
from test.st.executor.exec_parse import ExecParse
from test.st.checker.csv_checker import has_op_csv_files


def test_acl_prof_task_time_level_example(devices, mindie_path, dataset_path, model_path, tmp_workspace):
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
        mindie_server.set_prof_config(acl_task_time=1, enable=1, acl_prof_task_time_level="L1;18")
        assert benchmark.curl_test()

        # 查看acl_prof_task_time_level成功后相关日志打印
        acl_prof_task_time_level_exit_code, acl_prof_task_time_level_out = \
            mindie_server.wait("Profiler AclTaskTimeDuration 18 Seconds Is Reached, AclTaskTime Disabled Successfully!",
                               18)
        if acl_prof_task_time_level_exit_code is None and acl_prof_task_time_level_out == 0:
            acl_prof_task_time_level_success = True
        else:
            acl_prof_task_time_level_success = False
        assert acl_prof_task_time_level_success == True

        mindie_server.set_prof_config(acl_task_time=0, enable=0)
        mindie_server.kill()

        # 对采集文件夹中的特殊关键字进行校验
        key_name = '"profLevel":"l1"'
        check.is_true(grep_in_directory(prof_path, key_name), f"not found {key_name} in {prof_path}")

        # 开始解析
        parser = ExecParse()
        parser.set_input_path(prof_path)
        parser.set_output_path(os.path.join(workspace_path, "prof_data_out"))
        assert parser.ready_go()

        # 解析完了，开始校验相关文件的生成
        assert has_op_csv_files(os.path.join(workspace_path, "prof_data_out"))

    finally:
        if mindie_server:
            mindie_server.kill()
        print("workspace:", workspace_path)