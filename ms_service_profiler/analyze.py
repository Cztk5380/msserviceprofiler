# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import argparse
from pathlib import Path
from datetime import datetime, timezone

from ms_service_profiler.parse import parse
from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.exporters.utils import create_sqlite_db
from ms_service_profiler.plugins import custom_plugins
from ms_service_profiler.utils.log import set_log_level


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


def get_chlid_output_dir(output_path):
    current_datetime = datetime.now(tz=timezone.utc)
    datetime_str = current_datetime.strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_path, datetime_str)


def main():
    parser = argparse.ArgumentParser(description='MS Server Profiler')
    parser.add_argument(
        '--input_path',
        required=True,
        type=check_input_path_valid,
        help='Path to the folder containing profile data.')
    parser.add_argument(
        '--output_path',
        type=check_output_path_valid,
        default=os.path.join(os.getcwd(), 'output'),
        help='Output file path to save results.')
    parser.add_argument(
        '--log_level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        help='Log level to print')

    args = parser.parse_args()

    # 初始化日志等级
    set_log_level(args.log_level)

    # 初始化Exporter
    exporters = ExporterFactory.create_exporters(args)
    
    # 创建output目录
    Path(args.output_path).mkdir(parents=True, exist_ok=True)
    create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters)


if __name__ == '__main__':
    main()

