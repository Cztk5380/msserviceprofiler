# -*- coding: utf-8 -*-
# Copyright (c) 2025-2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


class BaseCSVFields(object):
    metric = "Metric"
    avg = "Average"
    max = "Max"
    min = "min"
    p50 = "P50"
    p90 = "P90"
    p99 = "P99"

    columns = (metric, avg, max, min, p50, p90, p99)


class BatchCSVFields(BaseCSVFields):
    prefill_batch_num = "prefill_batch_num"
    decode_batch_num = "decode_batch_num"
    prefill_exec_time = "prefill_exec_time (ms)"
    decode_exec_time = "decode_exec_time (ms)"

    path_name = "batch_summary.csv"

    metrics = (prefill_batch_num, decode_batch_num, prefill_exec_time, decode_exec_time)


class RequestCSVFields(BaseCSVFields):
    first_token_latency = "first_token_latency (ms)"
    subsequent_token_latency = "subsequent_token_latency (ms)"
    total_time = "total_time (ms)"
    exec_time = "exec_time (ms)"
    waiting_time = "waiting_time (ms)"
    input_token_num = "input_token_num"
    generated_token_num = "generated_token_num"

    path_name = "request_summary.csv"

    metrics = (
        first_token_latency, subsequent_token_latency, total_time,
        exec_time, waiting_time, input_token_num, generated_token_num
    )


class ServiceCSVFields(BaseCSVFields):
    value = "Value"
    total_input_token_num = "total_input_token_num"
    total_generated_token_num = "total_generated_token_num"
    generate_token_speed = "generate_token_speed (token/s)"
    generate_all_token_speed = "generate_all_token_speed (token/s)"

    path_name = "service_summary.csv"

    metrics = (
        total_input_token_num, total_generated_token_num,
        generate_token_speed, generate_all_token_speed
    )
    columns = (BaseCSVFields.metric, value)

