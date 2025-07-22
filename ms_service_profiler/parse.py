# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.
import os
import argparse
import subprocess
from pathlib import Path
import json
import re
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from json import JSONDecodeError
from collections import deque

import pandas as pd

from ms_service_profiler.task.task import Task
import ms_service_profiler.pipeline
import ms_service_profiler.data_source
from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.constant import US_PER_SECOND, MSPROF_REPORTS_PATH
from ms_service_profiler.plugins import (
    builtin_plugins, custom_plugins, PluginMsptiProcess, PluginEpBalanceProcess, PluginMoeSlowRankProcess
)
from ms_service_profiler.plugins.sort_plugins import sort_plugins
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.utils.timer import timer, Timer
from ms_service_profiler.utils.error import ParseError, LoadDataError
from ms_service_profiler.exporters.utils import (
    create_sqlite_db, check_input_path_valid, check_output_path_valid,
    find_file_in_dir, delete_dir_safely, find_all_file_complete
)


def get_mspti_db_filepaths(folder_path):
    filepaths = []
    # 合并后的正则表达式，同时验证文件名格式和提取通配符内容
    unified_pattern = re.compile(r'^ascend_service_profiler_(.+)\.db$')

    for fp in Path(folder_path).rglob('*'):  # 遍历所有文件
        match = unified_pattern.match(fp.name)
        if fp.is_file() and match:
            filepaths.append((str(fp), match.group(1)))
    return filepaths


def read_mspti_db(input_path):
    paths_and_pid = get_mspti_db_filepaths(input_path)
    data_list = []
    for db_path, db_id in paths_and_pid:
        try:
            api_df, kernel_df, communication_df = load_ops_db(db_path, db_id)
            data_list.append(
                dict(
                    api_df=api_df,
                    kernel_df=kernel_df,
                    communication_df=communication_df,
                    db_id=db_id
                )
            )
        except Exception as ex:
            raise LoadDataError(db_path) from ex
    return data_list


def load_ops_db(filepath, db_id):
    with sqlite3.connect(filepath) as conn:
        api_query = """
        SELECT name, start, end, processId, threadId, correlationId FROM Api order by correlationId asc
        """
        kernel_query = """
        SELECT name, type, start, end, deviceId, streamId, correlationId FROM Kernel order by correlationId asc
        """
        communication_query = """
        SELECT name, start, end, deviceId, streamId, dataCount, dataType, commGroupName, correlationId FROM Communication 
        order by correlationId asc
        """
        api_df = pd.read_sql_query(api_query, conn)
        kernel_df = pd.read_sql_query(kernel_query, conn)
        communication_df = pd.read_sql_query(communication_query, conn)
        api_df["db_id"] = db_id
        kernel_df["db_id"] = db_id
        communication_df["db_id"] = db_id
    return api_df, kernel_df, communication_df


def check_sub_profiler_path(input_path):
    # 判断子目录是否有PROF文件夹 如果有则走原来解析逻辑返回True 如果没有尝试走mspti返回False
    input_path = Path(input_path)
    for fp in Path(input_path).rglob('**'):
        if "PROF_" in fp.name:
            return True
    for fp in input_path.glob('*'):
        if "ms_service" in fp.name:
            return True  # 存在文件名包含'ms_service'的文件
    return False


def parse(input_path, plugins, exporters, **kwargs):
    # Compatible with blue zone calls
    parse_run(input_path=input_path, exporters=exporters, args=kwargs.get("args"))


def build_task_dag(exporters):
    next_tasks, prev_tasks, head_tasks = dict(), dict(), set()

    tasks = list(exporters)
    walking_index = 0

    while walking_index < len(tasks):
        walking_task_name = tasks[walking_index]
        walking_index += 1
        if isinstance(walking_task_name, Task):
            walking_task = walking_task_name
            walking_task_name = walking_task.name
        else:
            walking_task = Task.get_retister_by_name(walking_task_name)

        depend_names = walking_task.depends()
        if depend_names is None or len(depend_names) == 0:
            head_tasks.add(walking_task_name)
            continue
        tasks.extend(depend_names)
        prev_tasks[walking_task_name] = depend_names
        for depend_name in depend_names:
            next_tasks.setdefault(depend_name, set())
            next_tasks[depend_name].add(walking_task_name)

    return next_tasks, prev_tasks, head_tasks


def get_task_run_order(head_tasks, next_tasks, prev_tasks):
    ordered_tasks = list()
    done_tasks = set()
    walking_queue = deque()
    walking_queue.extend(head_tasks)
    while (walking_queue):
        task_name = walking_queue.popleft()
        if task_name in done_tasks:
            continue
        if all(prev_task in done_tasks for prev_task in prev_tasks.get(task_name, [])):
            ordered_tasks.append(task_name)
            done_tasks.add(task_name)
            walking_queue.extend(next_tasks.get(task_name, []))
        else:
            walking_queue.append(task_name)

    return ordered_tasks


def get_task_by_name(name, task_results, args):
    task = Task.get_retister_by_name(name)(args)
    depends = task.depends()
    has_depends_data = False
    for depend_name in depends:
        has_depends_data = has_depends_data or depend_name in task_results
        task.set_depends_result(depend_name, task_results.get(depend_name))
    return task, has_depends_data


def run_task(task, task_results):
    try:
        task_results[task.name] = task.run()
    except Exception as e:
        logger.error(f"task {task.name} in failed, message: {e}")
        task_results[task.name] = e
    else:
        logger.info(f'task {task.name} is done.')


def parse_run(input_path, exporters, args=None):
    logger.info('Start to parse.')
    exporter_new = []
    for exporter in exporters:
        if exporter.is_provide(args.format):
            if isinstance(exporter, Task):
                exporter_new.append(exporter)
            else:
                exporter_new.append(exporter(args))
    exporters = exporter_new
    exporter_names = [exporter.name for exporter in exporters]
    next_tasks, prev_tasks, data_source_tasks = build_task_dag(exporters)
    ordered_tasks = get_task_run_order(data_source_tasks, next_tasks, prev_tasks)

    def is_pipeline(task, batch):
        if task in exporter_names or task in data_source_tasks:
            return False
        return batch != Task.get_retister_by_name(task).is_deal_single_data()

    single_data_tasks_ordered = [x for x in ordered_tasks if is_pipeline(x, batch=False)]
    batch_data_tasks_ordered = [x for x in ordered_tasks if is_pipeline(x, batch=True)]
    batch_data_tasks_depends = []

    for task_name in batch_data_tasks_ordered:
        for prev_task_name in prev_tasks.get(task_name):
            if prev_task_name in single_data_tasks_ordered or prev_task_name in data_source_tasks:
                batch_data_tasks_depends.append(prev_task_name)

    with Timer("single_prof_data_tasks", logger.info):
        data = parallel_run_single_prof_data_tasks(data_source_tasks, single_data_tasks_ordered,
            batch_data_tasks_depends, input_path, args)

    err_msg = []
    batch_data = dict()
    for res_dict in data:
        if isinstance(res_dict, Exception):
            err_msg.append(res_dict)
            continue

        for key, value in res_dict.items():
            batch_data.setdefault(key, [])
            batch_data[key].append(value)

    for task_name in batch_data_tasks_ordered:
        task_ins, _ = get_task_by_name(task_name, batch_data, args)
        run_task(task_ins, batch_data)

    logger.info('Starting exporter processes.')
    with ProcessPoolExecutor() as executor:
        futures = {}
        for exporter in exporters:
            for prev_task in prev_tasks.get(exporter.name):
                exporter.set_depends_result(
                    prev_task, batch_data.get(prev_task))
            futures[exporter.name] = executor.submit(exporter.run)

        for exporter_name, future in futures.items():
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error raise from exporter: {exporter_name}, message: {e}")

    logger.info('Exporter done.')


def parallel_run_single_prof_data_tasks(data_source_tasks, single_data_tasks_ordered,
    batch_data_tasks_depends, input_path, args):

    with ProcessPoolExecutor() as executor:
        single_prof_index = 0
        future_map = dict()
        multi_tasks = []
        for data_source_name in data_source_tasks:
            data_source = Task.get_retister_by_name(data_source_name)(args)
            prof_paths = data_source.get_prof_paths(input_path)
            multi_tasks.append((data_source, prof_paths))

        for data_source, prof_paths in multi_tasks:
            for prof_path in prof_paths:
                single_prof_index += 1

                future = executor.submit(run_single_prof_data_tasks,
                              data_source, single_data_tasks_ordered, batch_data_tasks_depends, prof_path, args)
                future_map[(str(prof_path), single_prof_index)] = future

        def get_future_result(future, prof_info):
            prof_path, single_prof_index = prof_info
            try:
                return future.result()
            except Exception as e:
                err_msg = f"Error raise parsing [{single_prof_index}]{prof_path}, message: {e}"
                logger.error(err_msg)
                return ParseError(err_msg)

        return [get_future_result(future, prof_info)
                for prof_info, future in future_map.items()]


def run_single_prof_data_tasks(data_source_task, tasks, batch_data_tasks_depends, prof_path, args):
    task_results = dict()
    data_source_task.set_prof_path(prof_path)

    run_task(data_source_task, task_results)
    for task_name in tasks:
        task_ins, has_depends_data = get_task_by_name(task_name, task_results, args)
        if has_depends_data:
            run_task(task_ins, task_results)

    return {k: v for k, v in task_results.items() if k in batch_data_tasks_depends}


def main():
    parser = argparse.ArgumentParser(description='MS Server Profiler')
    parser.add_argument(
        '--input-path',
        required=True,
        type=check_input_path_valid,
        help='Path to the folder containing profile data.')
    parser.add_argument(
        '--output-path',
        type=check_output_path_valid,
        default=os.path.join(os.getcwd(), 'output'),
        help='Output file path to save results.')
    parser.add_argument(
        '--log-level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        help='Log level to print')
    parser.add_argument(
        '--format',
        nargs='+',
        default=['db', 'csv', 'json'],
        choices=['db', 'csv', 'json'],
        help='Format to save')

    args = parser.parse_args()

    # 初始化日志等级
    set_log_level(args.log_level)

    exporters = ExporterFactory.create_exporters(args)

    if 'db' in args.format:
        create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters, args=args)


if __name__ == '__main__':
    main()
