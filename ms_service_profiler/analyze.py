# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from ms_service_profiler.parse import parse
from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.exporters.utils import create_sqlite_db
from ms_service_profiler.plugins import custom_plugins
from ms_service_profiler.utils.log import set_log_level, logger
from ms_service_profiler.utils.file_open_check import FileStat


def check_input_path_valid(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path does not exist: {path}")
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"Path is not a valid directory: {path}")
    if '..' in path:
        raise argparse.ArgumentTypeError(f"Path contains illegal characters: {path}")
    return path


def check_output_path_valid(path):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        os.makedirs(path, mode=0o755)
    else:
        os.chmod(path, 0o755)
    if not os.access(path, os.W_OK):
        raise argparse.ArgumentTypeError(f"Output path is not writable: {path}")
    return path


def find_file_in_dir(directory, filename):
    for _, _, files in os.walk(directory):
        if filename in files:
            return True
    return False


def gen_msprof_command(full_path):
    try:
        FileStat(full_path)
    except Exception as err:
        raise argparse.ArgumentTypeError(f"input path:{input_path} is illegal. Please check.") from err

    command = "msprof --export=on "
    output_param = f"--output={full_path}"
    return command + output_param


def run_msprof_command(command):
    command_list = command.split()
    try:
        subprocess.run(command_list, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"msprof error: {e}")
    except Exception as e:
        logger.error(f"msprof error occurred: {e}")


def preprocess_prof_folders(input_path):
    for root, dirs, _ in os.walk(input_path):
        for dir_name in dirs:
            full_path = os.path.join(root, dir_name)

            if dir_name.startswith('PROF_') and not find_file_in_dir(full_path, 'msproftx.db'):
                command = gen_msprof_command(full_path)
                logger.info(f"{command}")
                run_msprof_command(command)
    if not find_file_in_dir(input_path, 'msproftx.db'):
        raise ValueError("msprof failed! No msproftx.db file is generated.")


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

    args = parser.parse_args()

    # 初始化日志等级
    set_log_level(args.log_level)

    # msprof预处理
    preprocess_prof_folders(args.input_path)

    # 初始化Exporter
    exporters = ExporterFactory.create_exporters(args)
    
    # 创建output目录
    Path(args.output_path).mkdir(parents=True, exist_ok=True)
    create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters)


if __name__ == '__main__':
    main()

