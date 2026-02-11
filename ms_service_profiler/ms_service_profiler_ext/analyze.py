# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          http://license.coscl.org.cn/MulanPSL2
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------


import os
import argparse

from msguard import validate_args, Rule
from msguard.security.io import mkdir_s


def add_summary_exporter(func):
    from ms_service_profiler.ms_service_profiler_ext.exporters.exporter_summary import ExporterSummary

    def wrapper(args):
        default_exporters = func(args)

        summary_exporter = ExporterSummary()
        summary_exporter.initialize(args)

        return [summary_exporter] + default_exporters
    return wrapper


def arg_parse(subparsers):
    parser = subparsers.add_parser(
        "analyze", formatter_class=argparse.ArgumentDefaultsHelpFormatter, help="MS Server Profiler Analyze"
    )
    parser.add_argument(
        '--input-path',
        required=True,
        type=validate_args(Rule.input_dir_traverse),
        help='Path to the folder containing profile data.',
    )
    parser.add_argument(
        '--output-path',
        type=str,
        default=os.path.join(os.getcwd(), 'output'),
        help='Output file path to save results.')
    parser.add_argument(
        '--log-level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        help='Log level to print.')
    parser.add_argument(
        '--format', nargs='+', default=['json', 'csv', 'db'], choices=['json', 'csv', 'db'], help='Format to save.'
    )
    parser.add_argument(
        '--span',
        nargs='*',
        default=None,
        help='Select target span info'
    )
    parser.set_defaults(func=main)


def main(args):
    from ms_service_profiler.parse import parse
    from ms_service_profiler.plugins import custom_plugins
    from ms_service_profiler.utils.log import set_log_level
    from ms_service_profiler.exporters.factory import ExporterFactory
    from ms_service_profiler.exporters.utils import create_sqlite_db

    # 初始化日志等级
    set_log_level(args.log_level)

    # 初始化Exporter
    wrapped_create_exporters = add_summary_exporter(ExporterFactory.create_exporters)
    exporters = wrapped_create_exporters(args)

    # 创建output目录
    mkdir_s(args.output_path)
    if not Rule.output_dir._is_satisfied_by(args.output_path):
        raise argparse.ArgumentTypeError(f"Output path is not valid: {args.output_path!r}")
    create_sqlite_db(args.output_path)

    # 解析数据并导出
    parse(args.input_path, custom_plugins, exporters, args=args)
