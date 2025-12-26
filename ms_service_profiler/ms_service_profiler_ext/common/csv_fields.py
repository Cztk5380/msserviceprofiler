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



class BaseCSVFields(object):
    METRIC = "Metric"
    AVG = "Average"
    MAX = "Max"
    MIN = "Min"
    P50 = "P50"
    P90 = "P90"
    P99 = "P99"

    columns = (METRIC, AVG, MAX, MIN, P50, P90, P99)


class BatchCSVFields(BaseCSVFields):
    PREFILL_BATCH_NUM = "prefill_batch_num"
    DECODE_BATCH_NUM = "decode_batch_num"
    PREFILL_EXEC_TIME = "prefill_exec_time (ms)"
    DECODE_EXEC_TIME = "decode_exec_time (ms)"

    PATH_NAME = "batch_summary.csv"

    metrics = (PREFILL_BATCH_NUM, DECODE_BATCH_NUM, PREFILL_EXEC_TIME, DECODE_EXEC_TIME)


class RequestCSVFields(BaseCSVFields):
    FIRST_TOKEN_LATENCY = "first_token_latency (ms)"
    SUBSEQUENT_TOKEN_LATENCY = "subsequent_token_latency (ms)"
    TOTAL_TIME = "total_time (ms)"
    EXEC_TIME = "exec_time (ms)"
    WAITING_TIME = "waiting_time (ms)"
    INPUT_TOKEN_NUM = "input_token_num"
    GENERATED_TOKEN_NUM = "generated_token_num"

    PATH_NAME = "request_summary.csv"

    metrics = (
        FIRST_TOKEN_LATENCY, SUBSEQUENT_TOKEN_LATENCY, TOTAL_TIME,
        EXEC_TIME, WAITING_TIME, INPUT_TOKEN_NUM, GENERATED_TOKEN_NUM
    )


class ServiceCSVFields(BaseCSVFields):
    VALUE = "Value"
    TOTAL_INPUT_TOKEN_NUM = "total_input_token_num"
    TOTAL_GENERATED_TOKEN_NUM = "total_generated_token_num"
    GENERATE_TOKEN_SPEED = "generate_token_speed (token/s)"
    GENERATE_ALL_TOKEN_SPEED = "generate_all_token_speed (token/s)"

    PATH_NAME = "service_summary.csv"

    metrics = (
        TOTAL_INPUT_TOKEN_NUM, TOTAL_GENERATED_TOKEN_NUM,
        GENERATE_TOKEN_SPEED, GENERATE_ALL_TOKEN_SPEED
    )
    columns = (BaseCSVFields.METRIC, VALUE)
