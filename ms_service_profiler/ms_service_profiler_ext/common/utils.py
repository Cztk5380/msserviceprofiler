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


import re
try:
    from ms_service_profiler.utils.log import logger, LOG_LEVELS, set_logger, set_log_level
except ModuleNotFoundError:
    import logging

    LOG_LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "fatal": logging.FATAL,
        "critical": logging.CRITICAL,
    }


    def set_log_level(level="info"):
        if level.lower() in LOG_LEVELS:
            logger.setLevel(LOG_LEVELS.get(level.lower()))
        else:
            logger.warning("Set %s log level failed.", level)


    def set_logger(msit_logger):
        msit_logger.propagate = False
        msit_logger.setLevel(logging.INFO)
        if not msit_logger.handlers:
            stream_handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(process)s - %(name)s - %(levelname)s - %(message)s")
            stream_handler.setFormatter(formatter)
            msit_logger.addHandler(stream_handler)


    logger = logging.getLogger("msServiceProfiler")
    set_logger(logger)


def confirmation_interaction(prompt):
    confirm_pattern = re.compile(r'y(?:es)?', re.IGNORECASE)
    
    try:
        user_action = input(prompt)
    except Exception:
        return False
    
    return bool(confirm_pattern.match(user_action))
