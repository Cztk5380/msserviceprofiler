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

import json
from enum import Enum
from ms_service_profiler.mstx import service_profiler
from ms_service_profiler.utils.log import logger


torch_prof = None
torch_prof_total_steps = 0
torch_prof_current_step = 0
prof_current_step = 0


class MarkType(int, Enum):
    TYPE_EVENT = 0
    TYPE_METRIC = 1
    TYPE_SPAN = 2
    TYPE_LINK = 3


class Level(int, Enum):
    ERROR = 10  # 20260630 日落
    INFO = 20  # 20260630 日落
    DETAILED = 30  # 20260630 日落
    VERBOSE = 40  # 20260630 日落
    LEVEL_CORE_TRACE = 10  # 最核心的数据，请求关键事件，比如请求到达，请求返回，batch 大小，forward 时长
    LEVEL_OUTLIER_ENENT = 10  # 异常、关键事件。比如发生了Swap，或者发生了重计算
    LEVEL_NORMAL_TRACE = 20  # 普通 Trace 数据
    LEVEL_DETAILED_TRACE = 30  # 包含更多，更大量的详细信息
    L0 = 10
    L1 = 20
    L2 = 30


class Profiler:
    def __init__(self, profiler_level) -> None:
        self._enable = service_profiler.is_enable(profiler_level)
        self._attr = dict()
        self._name = None          # 事件或 Span 名称
        self._domain = None        # 域名
        self._span_handle = None

    @property
    def enable(self):
        return self._enable

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.span_end()

    def attr(self, key, value):
        self._attr[key] = value
        return self

    def domain(self, domain):
        self._enable = self._enable and service_profiler.is_domain_enable(domain)
        self._domain = domain
        return self

    def res(self, res):
        return self.attr("rid", res)

    def metric(self, metric_name, metric_value):
        return self.attr(f"{metric_name}=", metric_value)

    def metric_inc(self, metric_name, metric_value):
        return self.attr(f"{metric_name}+", metric_value)

    def metric_scope(self, scope_name, scope_value=0):
        return self.attr(f"scope#{scope_name}", scope_value)

    def metric_scope_as_req_id(self):
        return self.attr("scope#", "req")

    def _get_attrs_json(self):
        return json.dumps(self._attr) if self._attr else ""

    def launch(self):
        if not self._enable:
            return
        self._name = "Launch"
        self._attr["type"] = MarkType.TYPE_EVENT
        self._mark_event_ex()

    def link(self, from_rid, to_rid):
        if not self._enable:
            return
        self._name = "Link"
        self._attr.clear()
        self.attr("type", MarkType.TYPE_LINK).attr("from", from_rid).attr("to", to_rid)
        self._mark_event_ex()

    def event(self, event_name):
        if not self._enable:
            return
        self._name = event_name
        self._attr["type"] = MarkType.TYPE_EVENT
        self._mark_event_ex()

    def span_start(self, span_name):
        if not self._enable:
            return self
        self._name = span_name
        self._attr["type"] = MarkType.TYPE_SPAN
        self._span_handle = service_profiler.start_span(span_name)
        return self

    def span_end(self):
        if not self._enable or self._span_handle is None:
            return

        msg = self._get_attrs_json()
        domain = self._domain or ""
        span_name = self._name
        service_profiler.span_end_ex(span_name, domain, msg, self._span_handle)

        self._span_handle = None

    def _mark_event_ex(self):
        if not self._enable:
            return

        msg = self._get_attrs_json()
        domain = self._domain or ""
        name = self._name
        service_profiler.mark_event_ex(name, domain, msg)

    def add_meta_info(self, meta_key, meta_data):
        if self._enable:
            service_profiler.add_meta_info(meta_key, str(meta_data))


def initialize_profiler():
    global torch_prof, torch_prof_total_steps, torch_prof_current_step
    import torch
    import torch_npu

    task_level_map = {"L0": torch_npu.profiler.ProfilerLevel.Level0, "L1": torch_npu.profiler.ProfilerLevel.Level1,
                      "L2": torch_npu.profiler.ProfilerLevel.Level2}

    aicore_metrics_map = {
        0: torch_npu.profiler.AiCMetrics.ArithmeticUtilization,
        1: torch_npu.profiler.AiCMetrics.PipeUtilization,
        2: torch_npu.profiler.AiCMetrics.Memory,
        3: torch_npu.profiler.AiCMetrics.MemoryL0,
        4: torch_npu.profiler.AiCMetrics.ResourceConflictRatio,
        5: torch_npu.profiler.AiCMetrics.MemoryUB,
        6: torch_npu.profiler.AiCMetrics.L2Cache,
        8: torch_npu.profiler.AiCMetrics.MemoryAccess,
    }

    profiler_level = task_level_map.get(service_profiler.get_acl_task_time_level(),
        torch_npu.profiler.ProfilerLevel.Level_none)

    aic_metrics = aicore_metrics_map.get(service_profiler.get_acl_prof_aicore_metrics(),
        torch_npu.profiler.AiCMetrics.AiCoreNone)

    experimental_config = torch_npu.profiler._ExperimentalConfig(
        export_type=torch_npu.profiler.ExportType.Text, profiler_level=profiler_level, msprof_tx=False,
        aic_metrics=aic_metrics, l2_cache=False, op_attr=False, data_simplification=False, record_op_args=False,
        gc_detect_threshold=None,)

    profiler_kwargs = {
        "activities": [torch_npu.profiler.ProfilerActivity.CPU,
                       torch_npu.profiler.ProfilerActivity.NPU],
        "on_trace_ready": torch_npu.profiler.tensorboard_trace_handler(
            dir_name=service_profiler.get_prof_path(),
            analyse_flag=False),
        "record_shapes": True,
        "profile_memory": False,
        "with_stack": service_profiler.is_torch_prof_stack(),
        "with_modules": service_profiler.is_torch_prof_modules(),
        "with_flops": False,
        "experimental_config": experimental_config,
    }

    prof_current_step = 0
    torch_prof_total_steps = service_profiler.get_torch_prof_step_num()
    if torch_prof_total_steps > 0:
        profiler_kwargs["schedule"] = torch_npu.profiler.schedule(
            wait=0, warmup=0, active=torch_prof_total_steps, repeat=1, skip_first=0)
        torch_prof_current_step = 0
        logger.info(f"Torch Profiler will run for a total of {torch_prof_total_steps} steps")

    torch_prof = torch_npu.profiler.profile(**profiler_kwargs)
    torch_prof.start()
    logger.info(f"Torch Profiler has started")


def prof_step(stop_check=False):
    global torch_prof, torch_prof_total_steps, torch_prof_current_step, prof_current_step

    if not stop_check:
        prof_current_step += 1
        service_profiler.set_profiler_current_step(prof_current_step)

    if not service_profiler.is_torch_profiler_enable(Level.L0):
        if torch_prof:
            torch_prof.stop()
            torch_prof = None
            logger.info(f"Torch Profiler has stopped")
        return

    if stop_check:
        return

    if not torch_prof:
        initialize_profiler()

    if torch_prof:
        if torch_prof_total_steps > 0:
            torch_prof_current_step += 1
            if torch_prof_current_step <= torch_prof_total_steps:
                logger.info(f"Torch Profiler is running step {torch_prof_current_step}/{torch_prof_total_steps}")

            prof = Profiler(Level.L0)
            prof.span_start("torch_profiler")
            torch_prof.step()
            prof.span_end()
