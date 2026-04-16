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

from typing import Dict
from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.meta_state import get_meta_state
from ms_service_metric.metrics.metrics_manager import get_metrics_manager, MetricType, SIZE_BUCKETS

metrics_client = get_metrics_manager()

logger = get_logger(__name__)


def init_data_parallel(original_func, this, vllm_config, *args, **kwargs):
    ret = original_func(this, vllm_config, *args, **kwargs)

    state = get_meta_state()

    # 若此进程还没采集过dpRankId,则添加meta数据
    if not state.has("dp_rank") or state.dp_rank == -1:
        logger.debug("Meta hook get dp_rank: %s", this.dp_rank)
        state.dp_rank = this.dp_rank

    return ret


def ensure_dp_rank_meta_collected(worker_instance) -> None:
    """
    若当前进程尚未采集过 dpRankId，则从 Worker/ModelRunner 实例上取 dp_rank 并写入 Meta。
    用于多 DP 多 TP 场景下，让仅运行 Worker 的进程也能上报 dp_rank，使 batch.csv 的 dp_rank 列可被正确填充。
    与 init_data_parallel（Engine 侧）共用 MetaCollectionState，每个进程只写入一次。
    """
    state = get_meta_state()
    if state.has("dp_rank") and state.dp_rank != -1:
        return
    dp_rank = getattr(worker_instance, "dp_rank", None)
    if dp_rank is None:
        pc = getattr(worker_instance, "parallel_config", None)
        dp_rank = getattr(pc, "data_parallel_rank", -1) if pc is not None else -1
    if dp_rank is None:
        dp_rank = -1
    logger.debug("Meta hook (worker) get dp_rank: %s", dp_rank)
    state.dp_rank = dp_rank


def init_data_parallel_worker(original_func, this, *args, **kwargs):
    """Worker 进程侧采集 dp_rank：首次进入 execute_model 时从 ModelRunner 取 data_parallel_rank 并写入 Meta。"""
    ensure_dp_rank_meta_collected(this)
    return original_func(this, *args, **kwargs)


TOTAL_KVCACHE_BLOCKS = "total_kvcache_blocks"
FREE_KVCACHE_BLOCKS = "free_kvcache_blocks"
ALLOCATED_KVCACHE_BLOCKS = "allocated_kvcache_blocks"
metrics_client.get_or_create_metric(TOTAL_KVCACHE_BLOCKS, metric_type=MetricType.GAUGE)
metrics_client.get_or_create_metric(FREE_KVCACHE_BLOCKS, metric_type=MetricType.GAUGE)
metrics_client.get_or_create_metric(ALLOCATED_KVCACHE_BLOCKS, metric_type=MetricType.GAUGE)


def make_stats(original_func, this, *args, **kwargs):
    state = get_meta_state()

    # 获取各dp kvcache
    kv_pool = this.kv_cache_manager.block_pool

    # 总block数量
    total_blocks = kv_pool.num_gpu_blocks

    # 剩余的block数量
    free_blocks = kv_pool.get_num_free_blocks()

    # 已经分配的block数量
    # 注意：需要减去null_block（block_id=0），它始终被占用
    allocated_blocks = total_blocks - free_blocks - 1

    kvcache_values_list = {
        TOTAL_KVCACHE_BLOCKS: total_blocks,
        FREE_KVCACHE_BLOCKS: free_blocks,
        ALLOCATED_KVCACHE_BLOCKS: allocated_blocks,
    }

    # 记录block数量metrics
    labels = {"dp": state.dp_rank}
    for kv_metric_name, values in kvcache_values_list.items():
        metrics_client.record_metric(kv_metric_name, labels=labels, value=values)

    ret = original_func(this, *args, **kwargs)

    # 传递dp域值，在record函数中捕获
    if ret.kv_connector_stats is None:
        ret.kv_connector_stats = {"dp": state.dp_rank}
    else:
        ret.kv_connector_stats["dp"] = state.dp_rank

    return ret


BATCH_SIZE = "batch_size"
WAITING_BATCH_SIZE = "waiting_batch_size"
NUM_SPEC_TOKENS = "num_spec_tokens"
metrics_client.get_or_create_metric(BATCH_SIZE, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(WAITING_BATCH_SIZE, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(NUM_SPEC_TOKENS, buckets=SIZE_BUCKETS, label_names=["engine"])


def _record_scheduler_metrics(scheduler_stats, labels: Dict[str, str]):
    if not scheduler_stats:
        logger.debug("No scheduler stats")
        return

    metrics_client.record_metric(BATCH_SIZE, labels=labels, value=scheduler_stats.num_running_reqs)
    metrics_client.record_metric(WAITING_BATCH_SIZE, labels=labels, value=scheduler_stats.num_waiting_reqs)

    if scheduler_stats.spec_decoding_stats and scheduler_stats.spec_decoding_stats.num_spec_tokens is not None:
        metrics_client.record_metric(NUM_SPEC_TOKENS, labels=labels, value=scheduler_stats.spec_decoding_stats.num_spec_tokens)


TOTAL_TOKENS = "total_tokens"
SECOND_TOKEN_LATENCY = "second_token_latency"
INPUT_METRICS = "input"
OUTPUT_METRICS = "output"
FINE_GRAINED_TTFT = "fine_grained_ttft"
FINE_GRAINED_TPOT = "fine_grained_tpot"


metrics_client.get_or_create_metric(TOTAL_TOKENS, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(SECOND_TOKEN_LATENCY, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(INPUT_METRICS, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(OUTPUT_METRICS, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(FINE_GRAINED_TTFT, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(FINE_GRAINED_TPOT, buckets=SIZE_BUCKETS, label_names=["engine"])


def _record_iteration_metrics(iteration_stats, labels: Dict[str, str]):
    if not iteration_stats:
        logger.debug("No iteration stats")
        return

    # Total tokens
    if iteration_stats.num_prompt_tokens is not None and iteration_stats.num_generation_tokens is not None:
        total_tokens = iteration_stats.num_prompt_tokens + iteration_stats.num_generation_tokens
        metrics_client.record_metric(TOTAL_TOKENS, labels=labels, value=total_tokens)

    # Second token latency
    if iteration_stats.inter_token_latencies_iter and len(iteration_stats.inter_token_latencies_iter) > 0:
        metrics_client.record_metric(SECOND_TOKEN_LATENCY, labels=labels, value=iteration_stats.inter_token_latencies_iter[0])

    # Input metrics
    if iteration_stats.num_prompt_tokens is not None:
        metrics_client.record_metric(INPUT_METRICS, labels=labels, value=iteration_stats.num_prompt_tokens)

    # Output metrics
    if iteration_stats.num_generation_tokens is not None:
        metrics_client.record_metric(OUTPUT_METRICS, labels=labels, value=iteration_stats.num_generation_tokens)

    # Fine-grained TTFT
    if iteration_stats.time_to_first_tokens_iter:
        for ttft in iteration_stats.time_to_first_tokens_iter:
            metrics_client.record_metric(FINE_GRAINED_TTFT, labels=labels, value=ttft)

    # Fine-grained TPOT
    if iteration_stats.finished_requests:
        for finished_request in iteration_stats.finished_requests:
            metrics_client.record_metric(FINE_GRAINED_TPOT, labels=labels, value=finished_request.mean_time_per_output_token)


def record(original_func, this, scheduler_stats, iteration_stats, mm_cache_stats, engine_idx, *args, **kwargs):
    labels = {"engine": engine_idx}
    ret = original_func(this, scheduler_stats, iteration_stats, mm_cache_stats, engine_idx, *args, **kwargs)

    _record_scheduler_metrics(scheduler_stats, labels)
    _record_iteration_metrics(iteration_stats, labels)
    return ret


def record_dp_rank(original_func, this, scheduler_stats, *args, **kwargs):
    # 删除临时数据
    if scheduler_stats is not None and scheduler_stats.kv_connector_stats is not None:
        dp_rank = scheduler_stats.kv_connector_stats.pop("dp", None)
        if dp_rank is not None and dp_rank != -1:
            state = get_meta_state()
            if (not state.has("dp_rank") or state.dp_rank == -1):
                state.dp_rank = dp_rank
        # 如果字典变空则恢复为 None
        if scheduler_stats.kv_connector_stats == {}:
            scheduler_stats.kv_connector_stats = None

    return original_func(this, scheduler_stats, *args, **kwargs)
