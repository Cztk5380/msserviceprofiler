# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import argparse
from ms_service_profiler.utils.log import logger, set_log_level
from ms_service_profiler.tracer.otlp_forward_service import OTLPForwarderService


def main():
    parser = argparse.ArgumentParser(description='MS Server Profiler Trace')
    parser.add_argument(
        '--log-level',
        type=str,
        default='info',
        choices=['debug', 'info', 'warning', 'error', 'fatal', 'critical'],
        help='Log level to print')

    args = parser.parse_args()

    set_log_level(args.log_level)

    try:
        service = OTLPForwarderService()
        service.start()
    except Exception as e:
        logger.warning(f"Start OTLPForwarderService failed: {e}")


if __name__ == '__main__':
    main()
