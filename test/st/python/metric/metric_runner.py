# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from executor.exec_vllm_server import ExecVLLMServer
from metric.metric_assertions import assert_metric_expectations
from metric.metric_scenarios import ScenarioContext, get_scenario
from metric.metric_smoke_utils import (
    PreflightReport,
    check_model_path,
    check_npu,
    choose_service_port,
    fetch_text,
    install_metric_source,
    prepare_prometheus_dir,
    require_command,
    restart_metric_collection,
    wait_http_ok,
)


@dataclass
class MetricRunnerConfig:
    scenario: str
    model_path: str
    devices: list[int]
    workspace: str
    debug: bool = False
    metric_source: str = "https://gitcode.com/Ascend/msserviceprofiler.git"
    metric_ref: str = "master"
    metric_install_mode: str = "editable"
    metric_service_port: int | None = None
    metric_skip_npu_busy_check: bool = False
    metric_npu_memory_threshold: int = 90
    vllm_extra_args: list[str] = field(default_factory=list)
    metric_request_count: int = 1


def run_metric_scenario(config: MetricRunnerConfig) -> None:
    artifact_dir = Path(config.workspace) / "metric-smoke" / config.scenario / uuid.uuid4().hex
    artifact_dir.mkdir(parents=True, exist_ok=True)
    scenario = get_scenario(config.scenario)
    server = None
    benchmark = None
    succeeded = False
    report = PreflightReport()

    try:
        if config.metric_request_count < 1:
            report.fail("request", f"metric request count must be >= 1, got {config.metric_request_count}")
        require_command("vllm", report)
        require_command("curl", report)
        check_model_path(config.model_path, report)
        selected_devices = check_npu(
            config.devices,
            skip_busy_check=config.metric_skip_npu_busy_check,
            memory_threshold=config.metric_npu_memory_threshold,
            report=report,
        )
        port = choose_service_port(config.metric_service_port, report)
        prom_dir = prepare_prometheus_dir(str(artifact_dir), report)

        context = ScenarioContext(
            model_path=config.model_path,
            devices=selected_devices,
            port=port,
            artifact_dir=artifact_dir,
            request_count=config.metric_request_count,
        )
        scenario.preflight(context, report)
        (artifact_dir / "preflight.log").write_text(str(report), encoding="utf-8")
        print(report)

        install_info = install_metric_source(
            source=config.metric_source,
            ref=config.metric_ref,
            install_mode=config.metric_install_mode,
            workspace=str(artifact_dir),
        )
        (artifact_dir / "metric_install.json").write_text(
            json.dumps(install_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        service_env = {
            "PROMETHEUS_MULTIPROC_DIR": prom_dir,
            "ASCEND_RT_VISIBLE_DEVICES": ",".join(str(device) for device in selected_devices),
        }
        service_env.update(scenario.build_service_env(context))
        vllm_args = scenario.build_vllm_args(context, config.vllm_extra_args)
        print(f"[metric-scenario] name={scenario.name}")
        print(f"[metric-scenario] devices={selected_devices}")
        print(f"[metric-scenario] request_count={context.request_count}")
        print(f"[metric-scenario] vllm_args={vllm_args}")
        for expectation in scenario.expectations():
            print(
                "[metric-expectation] "
                f"required={expectation.required}, forbidden={expectation.forbidden}, "
                f"names={expectation.names}, rules={expectation.rules}, "
                f"labels={expectation.labels}, desc={expectation.description}"
            )
        server = ExecVLLMServer(
            model_path=config.model_path,
            port=port,
            env=service_env,
            extra_args=vllm_args,
            startup_timeout=scenario.startup_timeout,
        )
        assert server.ready_go(), (
            f"vLLM service startup failed.\nArtifacts: {artifact_dir}\nService log tail:\n{server.get_output_tail()}"
        )
        scenario.validate_startup(server.get_output_tail(500))
        wait_http_ok(f"http://127.0.0.1:{port}/health")

        restart_metric_collection()
        benchmark = scenario.run_requests(context)

        metrics_text = fetch_text(f"http://127.0.0.1:{port}/metrics")
        (artifact_dir / "metrics.raw").write_text(metrics_text, encoding="utf-8")
        assert_metric_expectations(
            metrics_text,
            scenario.expectations(),
            report_path=artifact_dir / "assertion_report.json",
        )
        succeeded = True
    finally:
        (artifact_dir / "preflight.log").write_text(str(report), encoding="utf-8")
        if benchmark:
            (artifact_dir / "request.log").write_text(benchmark.get_output_tail(200), encoding="utf-8")
        if server:
            (artifact_dir / "service.log").write_text(server.get_output_tail(500), encoding="utf-8")
            server.kill()
        if succeeded and not config.debug:
            shutil.rmtree(artifact_dir, ignore_errors=True)
        else:
            print(f"metric smoke artifacts: {artifact_dir}")
