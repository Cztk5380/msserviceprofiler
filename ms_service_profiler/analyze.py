# Copyright (c) 2024-2024 Huawei Technologies Co., Ltd.

import os
import argparse
from pathlib import Path

from ms_service_profiler.parse import parse
from ms_service_profiler.exporters.factory import ExporterFactory
from ms_service_profiler.exporters.utils import check_input_path_valid, check_output_path_valid
from ms_service_profiler.plugins import custom_plugins
from ms_service_profiler.utils.log import set_log_level


def main():
    parser = argparse.ArgumentParser(description='MS Server Profiler Analyze')
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
    args.split = 'on'

    # 初始化日志等级
    set_log_level(args.log_level)

    # 初始化Exporter
    exporters = ExporterFactory.create_exporters(args)
    
    # 创建output目录
    Path(args.output_path).mkdir(parents=True, exist_ok=True)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters)


if __name__ == '__main__':
    main()

