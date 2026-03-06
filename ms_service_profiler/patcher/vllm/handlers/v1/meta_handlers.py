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
from ms_service_profiler import Profiler, Level
from ms_service_profiler.patcher.core.module_hook import patcher
from ms_service_profiler.patcher.core.metric_hook import get_hook_metrics
from ms_service_profiler.patcher.core.logger import logger
from ms_service_profiler.patcher.vllm.metrics.definitions import MetricConstants, MetricManager
from .utils import SharedHookState, create_state_getter


class MetaCollectionState(SharedHookState):
    def __init__(self):
        super().__init__()
        self.has_collected = False  # 添加状态标记属性
        self.dp_rank_id = -1  # dp域


# 线程本地存储获取器（每文件独立线程状态）
_get_state = create_state_getter(MetaCollectionState)


@patcher(("vllm.v1.engine.core", "DPEngineCoreProc.add_request"), min_version="0.9.1")
def init_data_parallel(original_func, this, vllm_config, *args, **kwargs):
    ret = original_func(this, vllm_config, *args, **kwargs)

    state = _get_state()

    metrics_client = get_hook_metrics()

    # 若此进程还没采集过dpRankId,则添加meta数据
    if not state.has_collected:
        logger.debug("Meta hook get dp_rank: %s", this.dp_rank)
        Profiler(Level.INFO).add_meta_info("dpRankId", this.dp_rank)
        state.has_collected = True  # 更新状态类中的属性

        # 更新metrics模块中dp域信息
        state.dp_rank_id = this.dp_rank
        metrics_client.meta_state = state

    return ret


def ensure_dp_rank_meta_collected(worker_instance) -> None:
    """
    若当前进程尚未采集过 dpRankId，则从 Worker/ModelRunner 实例上取 dp_rank 并写入 Meta。
    用于多 DP 多 TP 场景下，让仅运行 Worker 的进程也能上报 dp_rank，使 batch.csv 的 dp_rank 列可被正确填充。
    与 init_data_parallel（Engine 侧）共用 MetaCollectionState，每个进程只写入一次。
    """
    state = _get_state()
    if state.has_collected:
        return
    dp_rank = getattr(worker_instance, "dp_rank", None)
    if dp_rank is None:
        pc = getattr(worker_instance, "parallel_config", None)
        dp_rank = getattr(pc, "data_parallel_rank", -1) if pc is not None else -1
    if dp_rank is None:
        dp_rank = -1
    logger.debug("Meta hook (worker) get dp_rank: %s", dp_rank)
    Profiler(Level.INFO).add_meta_info("dpRankId", dp_rank)
    state.has_collected = True
    state.dp_rank_id = dp_rank
    metrics_client = get_hook_metrics()
    metrics_client.meta_state = state


def init_data_parallel_worker(original_func, this, *args, **kwargs):
    """Worker 进程侧采集 dp_rank：首次进入 execute_model 时从 ModelRunner 取 data_parallel_rank 并写入 Meta。"""
    ensure_dp_rank_meta_collected(this)
    return original_func(this, *args, **kwargs)


@patcher(("vllm.v1.core.sched.scheduler", "Scheduler.make_stats"), min_version="0.9.1")
def make_stats(original_func, this, *args, **kwargs):
    state = _get_state()

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
        MetricConstants.TOTAL_KVCACHE_BLOCKS: total_blocks,
        MetricConstants.FREE_KVCACHE_BLOCKS: free_blocks,
        MetricConstants.ALLOCATED_KVCACHE_BLOCKS: allocated_blocks
    }

    # 记录block数量metrics
    labels = {"dp": state.dp_rank_id}
    for kv_metric_name, values in kvcache_values_list.items():
        MetricManager.record_metric(kv_metric_name, labels, values)

    ret = original_func(this, *args, **kwargs)

    # 传递dp域值，在record函数中捕获
    if ret.kv_connector_stats is None:
        ret.kv_connector_stats = {"dp": state.dp_rank_id}
    else:
        ret.kv_connector_stats["dp"] = state.dp_rank_id

    return ret


def _record_scheduler_metrics(scheduler_stats, labels: Dict[str, str]):
    if not scheduler_stats:
        return
    
    MetricManager.record_metric(MetricConstants.BATCH_SIZE, labels, scheduler_stats.num_running_reqs)
    MetricManager.record_metric(MetricConstants.WAITING_BATCH_SIZE, labels, scheduler_stats.num_waiting_reqs)

    if (scheduler_stats.spec_decoding_stats and 
        scheduler_stats.spec_decoding_stats.num_spec_tokens is not None):
        MetricManager.record_metric(MetricConstants.NUM_SPEC_TOKENS, labels,
                                    scheduler_stats.spec_decoding_stats.num_spec_tokens)


def _record_iteration_metrics(iteration_stats, labels: Dict[str, str]):
    if not iteration_stats:
        return
    
    # Total tokens
    if (iteration_stats.num_prompt_tokens is not None and 
        iteration_stats.num_generation_tokens is not None):
        total_tokens = iteration_stats.num_prompt_tokens + iteration_stats.num_generation_tokens
        MetricManager.record_metric(MetricConstants.TOTAL_TOKENS, labels, total_tokens)
    
    # Second token latency
    if (iteration_stats.inter_token_latencies_iter and 
        len(iteration_stats.inter_token_latencies_iter) > 0):
        MetricManager.record_metric(MetricConstants.SECOND_TOKEN_LATENCY, labels,
                                    iteration_stats.inter_token_latencies_iter[0])
    
    # Input metrics
    if iteration_stats.num_prompt_tokens is not None:
        MetricManager.record_metric(MetricConstants.INPUT_METRICS, labels,
                            iteration_stats.num_prompt_tokens)
    
    # Output metrics
    if iteration_stats.num_generation_tokens is not None:
        MetricManager.record_metric(MetricConstants.OUTPUT_METRICS, labels,
                    iteration_stats.num_generation_tokens)
    
    # Fine-grained TTFT
    if iteration_stats.time_to_first_tokens_iter:
        for ttft in iteration_stats.time_to_first_tokens_iter:
            MetricManager.record_metric(MetricConstants.FINE_GRAINED_TTFT, labels, ttft)
    
    # Fine-grained TPOT
    if iteration_stats.finished_requests:
        for finished_request in iteration_stats.finished_requests:
            MetricManager.record_metric(MetricConstants.FINE_GRAINED_TPOT, labels,
                                        finished_request.mean_time_per_output_token)


@patcher(("vllm.v1.metrics.loggers", "StatLoggerManager.record"), min_version="0.9.1")
def record(original_func, this, scheduler_stats, iteration_stats, *args, **kwargs):

    kv_stats = (scheduler_stats.kv_connector_stats
                if (scheduler_stats is not None and scheduler_stats.kv_connector_stats)
                else {})
    labels = {"dp": kv_stats.get("dp", -1)}

    # 删除临时数据
    if scheduler_stats is not None and scheduler_stats.kv_connector_stats is not None:
        scheduler_stats.kv_connector_stats.pop("dp", None)
        # 如果字典变空则恢复为 None
        if scheduler_stats.kv_connector_stats == {}:
            scheduler_stats.kv_connector_stats = None

    ret = original_func(this, scheduler_stats, iteration_stats, *args, **kwargs)

    _record_scheduler_metrics(scheduler_stats, labels)
    _record_iteration_metrics(iteration_stats, labels)

    return ret
