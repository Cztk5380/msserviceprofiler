# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from executor.exec_benchmark import ExecBenchmark
from metric.metric_assertions import MetricExpectation
from metric.metric_smoke_utils import MetricSmokeError, PreflightReport, run_command


class ScenarioUnavailable(MetricSmokeError):
    pass


@dataclass
class ScenarioContext:
    model_path: str
    devices: list[int]
    port: int
    artifact_dir: Path
    request_count: int = 1


@dataclass
class MetricScenario:
    name: str
    min_devices: int = 1
    startup_timeout: int = 900
    default_vllm_args: list[str] = field(default_factory=list)
    skip_if_unavailable: bool = False

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        if len(context.devices) < self.min_devices:
            self.unavailable(
                report,
                f"requires at least {self.min_devices} NPU device(s), got {context.devices}",
            )
        report.pass_(f"scenario:{self.name}", f"selected devices={context.devices}")

    def unavailable(self, report: PreflightReport, detail: str) -> None:
        if not self.skip_if_unavailable:
            report.fail(f"scenario:{self.name}", detail)
        report.lines.append(f"[preflight:scenario:{self.name}] SKIP: {detail}")
        raise ScenarioUnavailable(str(report))

    def build_vllm_args(self, context: ScenarioContext, extra_args: Optional[list[str]] = None) -> list[str]:
        return [*self.default_vllm_args, *(extra_args or [])]

    def build_service_env(self, context: ScenarioContext) -> dict[str, str]:
        return {}

    def validate_startup(self, service_output: str) -> None:
        return

    def run_requests(self, context: ScenarioContext) -> ExecBenchmark:
        return _run_completion_requests(context, count=context.request_count)

    def expectations(self) -> list[MetricExpectation]:
        raise NotImplementedError


def _run_completion_requests(context: ScenarioContext, count: int) -> ExecBenchmark:
    benchmark = ExecBenchmark()
    for request_index in range(count):
        if benchmark.curl_vllm_test(
            server_ip="127.0.0.1",
            server_port=context.port,
            model_path=context.model_path,
        ):
            continue
        raise MetricSmokeError(
            f"vLLM completion request {request_index + 1}/{count} failed. Artifacts: {context.artifact_dir}"
        )
    return benchmark


class BasicScenario(MetricScenario):
    def __init__(self):
        super().__init__(
            name="basic",
            min_devices=1,
            startup_timeout=900,
            default_vllm_args=["--enforce-eager", "--max-model-len", "2048"],
        )

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=[
                    "vllm_profiling_engine:generate:duration_count",
                    "vllm_profiling_engine_generate_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present", "phase": "present", "role": "present"},
                description="basic generate path should be profiled after one completion request",
            ),
            MetricExpectation(
                names=[
                    "vllm_profiling_scheduler:duration_count",
                    "vllm_profiling_scheduler_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present", "phase": "present", "role": "present"},
                description="scheduler should run during the basic completion request",
            ),
        ]


class EplbScenario(MetricScenario):
    def __init__(self):
        super().__init__(
            name="eplb",
            min_devices=2,
            startup_timeout=1200,
            skip_if_unavailable=True,
        )

    def run_requests(self, context: ScenarioContext) -> ExecBenchmark:
        return _run_completion_requests(context, count=max(4, context.request_count))

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        super().preflight(context, report)
        _require_moe_model(context.model_path, report, self)
        _require_import("vllm_ascend.eplb.core.eplb_worker", report, self)
        help_text = _get_vllm_help(report, self)
        for option in ("--tensor-parallel-size", "--enable-expert-parallel", "--additional-config"):
            _require_vllm_option(help_text, option, report, self)

    def build_vllm_args(self, context: ScenarioContext, extra_args: Optional[list[str]] = None) -> list[str]:
        eplb_config = {
            "eplb_config": {
                "dynamic_eplb": True,
                "expert_heat_collection_interval": 4,
                "algorithm_execution_interval": 1,
                "eplb_policy_type": 2,
                "num_redundant_experts": 4,
            }
        }
        return [
            "--tensor-parallel-size",
            str(len(context.devices)),
            "--enable-expert-parallel",
            "--max-model-len",
            "4096",
            "--additional-config",
            json.dumps(eplb_config, separators=(",", ":")),
            *(extra_args or []),
        ]

    def build_service_env(self, context: ScenarioContext) -> dict[str, str]:
        return {"DYNAMIC_EPLB": "true"}

    def validate_startup(self, service_output: str) -> None:
        if "Dynamic EPLB is True" not in service_output:
            raise MetricSmokeError("EPLB service started but startup logs did not confirm 'Dynamic EPLB is True'")

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=[
                    "vllm_profiling_eplb:expert_hotness:current_mean",
                    "vllm_profiling_eplb:expert_hotness:current_max",
                    "vllm_profiling_eplb:expert_hotness:imbalance",
                    "vllm_profiling_eplb:expert_map_update:duration_count",
                    "vllm_profiling_eplb:log2phy_map_update:duration_count",
                    "vllm_profiling_eplb:expert_weight_update:duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gte:0"],
                description="at least one EPLB-specific runtime metric must be emitted",
            ),
        ]


class DplbScenario(MetricScenario):
    def __init__(self):
        super().__init__(name="dplb", min_devices=2, startup_timeout=1200, skip_if_unavailable=True)

    def run_requests(self, context: ScenarioContext) -> ExecBenchmark:
        return _run_completion_requests(context, count=max(4, len(context.devices) * 2, context.request_count))

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        super().preflight(context, report)
        help_text = _get_vllm_help(report, self)
        _require_vllm_option(help_text, "--data-parallel-size", report, self)
        _require_vllm_option(help_text, "--data-parallel-hybrid-lb", report, self)

    def build_vllm_args(self, context: ScenarioContext, extra_args: Optional[list[str]] = None) -> list[str]:
        return [
            "--enforce-eager",
            "--max-model-len",
            "2048",
            "--data-parallel-size",
            str(len(context.devices)),
            "--data-parallel-hybrid-lb",
            *(extra_args or []),
        ]

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=[
                    "vllm_profiling_scheduler:duration_count",
                    "vllm_profiling_scheduler_duration_count",
                ],
                required=True,
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present"},
                min_distinct_labels={"dp": 2},
                description="DPLB scenario should expose scheduler metrics from multiple dp ranks",
            ),
        ]


class ExceptionScenario(MetricScenario):
    def __init__(self):
        super().__init__(name="exception", min_devices=1, startup_timeout=900, skip_if_unavailable=True)

    def preflight(self, context: ScenarioContext, report: PreflightReport) -> None:
        super().preflight(context, report)
        self.unavailable(
            report,
            "no deterministic health/RPC failure trigger is implemented yet; refusing a false-positive ST pass",
        )

    def expectations(self) -> list[MetricExpectation]:
        return [
            MetricExpectation(
                names=["vllm_profiling_health_check_failed_total"],
                required=False,
                rules=["exists", "finite", "gt:0"],
                description="health failure metric is optional until a stable failure trigger is added",
            )
        ]


SCENARIOS = {
    "basic": BasicScenario,
    "eplb": EplbScenario,
    "dplb": DplbScenario,
    "exception": ExceptionScenario,
}


def get_scenario(name: str) -> MetricScenario:
    try:
        return SCENARIOS[name]()
    except KeyError as exc:
        raise MetricSmokeError(f"Unknown metric scenario '{name}', choices: {sorted(SCENARIOS)}") from exc


def _require_import(module_name: str, report: PreflightReport, scenario: MetricScenario) -> None:
    try:
        __import__(module_name)
    except Exception as exc:
        scenario.unavailable(report, f"required module is unavailable: {module_name}, error={exc}")
    report.pass_(f"scenario:{scenario.name}", f"required module available: {module_name}")


def _require_moe_model(model_path: str, report: PreflightReport, scenario: MetricScenario) -> None:
    config_path = Path(model_path) / "config.json"
    if not config_path.exists():
        scenario.unavailable(report, f"MoE model check requires config.json under {model_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        scenario.unavailable(report, f"failed to read model config.json: {exc}")

    moe_keys = ("num_experts", "n_routed_experts", "moe_intermediate_size", "num_local_experts")
    if not any(key in config for key in moe_keys):
        scenario.unavailable(report, f"EPLB requires a MoE model config, missing keys {moe_keys}")
    report.pass_(f"scenario:{scenario.name}", "MoE model markers found")


def _get_vllm_help(report: PreflightReport, scenario: MetricScenario) -> str:
    result = run_command(["vllm", "serve", "--help=all"], timeout=60)
    if result.returncode != 0:
        result = run_command(["vllm", "serve", "--help"], timeout=60)
    if result.returncode != 0:
        scenario.unavailable(report, f"failed to inspect vLLM serve options:\n{result.stdout}")
    return result.stdout


def _require_vllm_option(
    help_text: str,
    option: str,
    report: PreflightReport,
    scenario: MetricScenario,
) -> None:
    if option not in help_text:
        scenario.unavailable(
            report,
            f"installed vLLM/vllm-ascend does not expose required option {option}",
        )
    report.pass_(f"scenario:{scenario.name}", f"vLLM option available: {option}")
