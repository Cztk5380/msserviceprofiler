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
from ms_service_metric.adapters.vllm.handlers.utils import (
    QUEUE_PHASES,
    collect_queue_phase_metrics,
    get_scheduler_phase_state,
)
from ms_service_metric.utils.logger import get_logger
from ms_service_metric.metrics.meta_state import get_meta_state
from ms_service_metric.metrics.metrics_manager import get_metrics_manager, MetricType, SIZE_BUCKETS

metrics_client = get_metrics_manager()

logger = get_logger(__name__)
_MISSING_QUEUE_ATTRS_WARNED = set()


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
RUNNING_PHASE_BATCH_SIZE = "running_phase_batch_size"
WAITING_PHASE_BATCH_SIZE = "waiting_phase_batch_size"
metrics_client.get_or_create_metric(TOTAL_KVCACHE_BLOCKS, metric_type=MetricType.GAUGE)
metrics_client.get_or_create_metric(FREE_KVCACHE_BLOCKS, metric_type=MetricType.GAUGE)
metrics_client.get_or_create_metric(ALLOCATED_KVCACHE_BLOCKS, metric_type=MetricType.GAUGE)
metrics_client.get_or_create_metric(RUNNING_PHASE_BATCH_SIZE, buckets=SIZE_BUCKETS, label_names=["req_phase"])
metrics_client.get_or_create_metric(WAITING_PHASE_BATCH_SIZE, buckets=SIZE_BUCKETS, label_names=["req_phase"])


def _with_phase_all(labels: Dict[str, str] | None = None) -> Dict[str, str]:
    fixed_labels = labels.copy() if labels is not None else {}
    fixed_labels.setdefault("phase", "all")
    return fixed_labels


def _record_queue_phase_metrics(metric_name: str, phase_counts: Dict[str, int]):
    for phase in QUEUE_PHASES:
        metrics_client.record_metric(
            metric_name,
            labels=_with_phase_all({"req_phase": phase}),
            value=phase_counts.get(phase, 0),
        )


def _get_scheduler_queue(scheduler, attr_name: str):
    if hasattr(scheduler, attr_name):
        return getattr(scheduler, attr_name)
    if attr_name not in _MISSING_QUEUE_ATTRS_WARNED:
        logger.warning("Scheduler has no %s queue attribute, phase queue metrics will be recorded as zero", attr_name)
        _MISSING_QUEUE_ATTRS_WARNED.add(attr_name)
    return []


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
    # KVCache block 数量是全局状态，不随迭代 phase 变化，因此固定 phase="all" 避免被 meta_state 的动态 phase 拆分为多条时间线
    labels = _with_phase_all({"dp": state.dp_rank})
    for kv_metric_name, values in kvcache_values_list.items():
        metrics_client.record_metric(kv_metric_name, labels=labels, value=values)
    ret = original_func(this, *args, **kwargs)
    phase_state = get_scheduler_phase_state()
    running_phase_counts = collect_queue_phase_metrics(phase_state, _get_scheduler_queue(this, "running"))
    waiting_phase_counts = collect_queue_phase_metrics(phase_state, _get_scheduler_queue(this, "waiting"))
    _record_queue_phase_metrics(RUNNING_PHASE_BATCH_SIZE, running_phase_counts)
    _record_queue_phase_metrics(WAITING_PHASE_BATCH_SIZE, waiting_phase_counts)

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

    labels = _with_phase_all(labels)
    metrics_client.record_metric(BATCH_SIZE, labels=labels, value=scheduler_stats.num_running_reqs)
    metrics_client.record_metric(WAITING_BATCH_SIZE, labels=labels, value=scheduler_stats.num_waiting_reqs)

    if scheduler_stats.spec_decoding_stats and scheduler_stats.spec_decoding_stats.num_spec_tokens is not None:
        metrics_client.record_metric(
            NUM_SPEC_TOKENS, labels=labels, value=scheduler_stats.spec_decoding_stats.num_spec_tokens
        )


TOTAL_TOKENS = "total_tokens"
SECOND_TOKEN_LATENCY = "second_token_latency"  # nosec B105
INPUT_METRICS = "input"
OUTPUT_METRICS = "output"
FINE_GRAINED_TTFT = "fine_grained_ttft"
FINE_GRAINED_TPOT = "fine_grained_tpot"
DECODE_OVER_1S_COUNT = "decode_over_1s_count"
PREFILL_OVER_THRESHOLD_COUNT = "prefill_over_threshold_count"

_PREFILL_THRESHOLDS = (("5s", 5.0), ("10s", 10.0), ("20s", 20.0))


metrics_client.get_or_create_metric(TOTAL_TOKENS, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(SECOND_TOKEN_LATENCY, buckets=SIZE_BUCKETS)
metrics_client.get_or_create_metric(INPUT_METRICS, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(OUTPUT_METRICS, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(FINE_GRAINED_TTFT, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(FINE_GRAINED_TPOT, buckets=SIZE_BUCKETS, label_names=["engine"])
metrics_client.get_or_create_metric(DECODE_OVER_1S_COUNT, metric_type=MetricType.COUNTER)
metrics_client.get_or_create_metric(
    PREFILL_OVER_THRESHOLD_COUNT,
    label_names=["threshold"],
    metric_type=MetricType.COUNTER,
)

_DECODE_LATENCY_THRESHOLD = 1.0


def _record_metric_safely(metric_name: str, value: int = 1, labels: Dict[str, str] | None = None) -> None:
    try:
        metrics_client.record_metric(metric_name, value, _with_phase_all(labels))
    except Exception as exc:
        logger.warning("Failed to record metric %s safely: %s", metric_name, exc)


def _record_slow_decode_metrics(iteration_stats):
    decode_count = sum(
        1
        for latency in (getattr(iteration_stats, "inter_token_latencies_iter", None) or [])
        if latency > _DECODE_LATENCY_THRESHOLD
    )
    if decode_count > 0:
        _record_metric_safely(DECODE_OVER_1S_COUNT, decode_count)


def _record_slow_prefill_metrics(iteration_stats):
    for threshold_label, threshold_value in _PREFILL_THRESHOLDS:
        prefill_count = sum(
            1 for ttft in (getattr(iteration_stats, "time_to_first_tokens_iter", None) or []) if ttft > threshold_value
        )
        if prefill_count > 0:
            _record_metric_safely(PREFILL_OVER_THRESHOLD_COUNT, prefill_count, {"threshold": threshold_label})


def iteration_stats_update_from_output_hooker(
    original_func,
    this,
    output,
    engine_core_timestamp,
    is_prefilling,
    *args,
    **kwargs,
):
    """Capture true second-token latency before vLLM flattens ITL samples.

    Compatible with both:
    - vLLM/vllm-ascend 0.14.0 style:
      (output, ts, is_prefilling, prompt_len, req_stats, lora_states, lora_name)
    - current upstream master style:
      (output, ts, is_prefilling, req_stats, lora_states, lora_name)
    """
    # 不同 vLLM 版本中 req_stats 的参数位置不同：
    # - v0.19.x 及以前（含 vllm-ascend 0.14.0 对应形态）：
    #   args[0] 是 prompt_len，args[1] 才是 req_stats
    # - v0.20.0 及以后：
    #   args[0] 直接就是 req_stats
    # 因此这里不写死位置，而是根据对象是否具备关键字段来识别真正的 req_stats。
    req_stats = kwargs.get("req_stats")
    if req_stats is None and args:
        first_arg = args[0]
        # v0.20.0 及以后：第一个额外位置参数就是 req_stats
        if hasattr(first_arg, "num_generation_tokens") and hasattr(first_arg, "last_token_ts"):
            req_stats = first_arg
        elif len(args) >= 2:
            second_arg = args[1]
            # v0.19.x 及以前：第一个额外位置参数是 prompt_len，第二个才是 req_stats
            if hasattr(second_arg, "num_generation_tokens") and hasattr(second_arg, "last_token_ts"):
                req_stats = second_arg

    previous_generation_tokens = getattr(req_stats, "num_generation_tokens", None)
    previous_token_ts = getattr(req_stats, "last_token_ts", None)
    ret = original_func(this, output, engine_core_timestamp, is_prefilling, *args, **kwargs)

    _record_slow_decode_metrics(this)
    _record_slow_prefill_metrics(this)

    if is_prefilling or previous_generation_tokens != 1 or previous_token_ts is None:
        return ret
    if engine_core_timestamp is None:
        return ret

    second_token_latency = engine_core_timestamp - previous_token_ts
    if second_token_latency >= 0:
        metrics_client.record_metric(
            SECOND_TOKEN_LATENCY,
            labels=_with_phase_all({"dp": get_meta_state().dp_rank}),
            value=second_token_latency,
        )

    return ret


def _record_iteration_metrics(iteration_stats, labels: Dict[str, str]):
    if not iteration_stats:
        logger.debug("No iteration stats")
        return

    labels = _with_phase_all(labels)

    # Total tokens
    if iteration_stats.num_prompt_tokens is not None and iteration_stats.num_generation_tokens is not None:
        total_tokens = iteration_stats.num_prompt_tokens + iteration_stats.num_generation_tokens
        metrics_client.record_metric(TOTAL_TOKENS, labels=labels, value=total_tokens)

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
            metrics_client.record_metric(
                FINE_GRAINED_TPOT, labels=labels, value=finished_request.mean_time_per_output_token
            )


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
            if not state.has("dp_rank") or state.dp_rank == -1:
                state.dp_rank = dp_rank
        # 如果字典变空则恢复为 None
        if scheduler_stats.kv_connector_stats == {}:
            scheduler_stats.kv_connector_stats = None

    return original_func(this, scheduler_stats, *args, **kwargs)
