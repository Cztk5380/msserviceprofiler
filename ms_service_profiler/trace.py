# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.

import argparse
import os
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

    if os.name != "nt" and os.getuid() == 0:
        logger.warning(
            "Security Warning: Do not run this tool as root. "
            "Running with elevated privileges may compromise system security. "
            "Run the program as the user who runs MindIE."
        )

    try:
        service = OTLPForwarderService()
        service.start()
    except Exception as e:
        logger.warning(f"Start OTLPForwarderService failed: {e}")


if __name__ == '__main__':
    main()
