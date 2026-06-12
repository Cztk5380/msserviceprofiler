# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import importlib
import json
import sys
from pathlib import Path

import pytest


ST_PYTHON_DIR = Path(__file__).resolve().parents[2] / "st" / "python"
sys.path.insert(0, str(ST_PYTHON_DIR))

metric_assertions = importlib.import_module("metric.metric_assertions")
metric_log_health = importlib.import_module("metric.metric_log_health")
metric_scenarios = importlib.import_module("metric.metric_scenarios")
metric_smoke_utils = importlib.import_module("metric.metric_smoke_utils")

MetricExpectation = metric_assertions.MetricExpectation
assert_metric_expectations = metric_assertions.assert_metric_expectations
parse_prometheus_text = metric_assertions.parse_prometheus_text
wait_for_metric_expectations = metric_assertions.wait_for_metric_expectations
assert_metric_log_health = metric_log_health.assert_metric_log_health
scan_metric_log_health = metric_log_health.scan_metric_log_health
ScenarioContext = metric_scenarios.ScenarioContext
get_scenario = metric_scenarios.get_scenario
MetricSmokeError = metric_smoke_utils.MetricSmokeError
_parse_visible_devices = metric_smoke_utils._parse_visible_devices


PROMETHEUS_TEXT = """
# TYPE vllm_profiling_engine:generate:duration histogram
vllm_profiling_engine:generate:duration_sum{dp="0",phase="mixed",role="mixed"} 0.25
vllm_profiling_engine:generate:duration_count{dp="0",phase="mixed",role="mixed"} 1
# TYPE vllm_profiling_scheduler:duration histogram
vllm_profiling_scheduler:duration_sum{dp="0",phase="prefill",role="mixed"} 0.5
vllm_profiling_scheduler:duration_count{dp="0",phase="prefill",role="mixed"} 2
optional_nan NaN
optional_inf +Inf
"""


def test_parse_prometheus_text_preserves_names_labels_and_special_values():
    samples = parse_prometheus_text(PROMETHEUS_TEXT)
    generate = next(sample for sample in samples if sample.name.endswith("generate:duration_count"))

    assert generate.value == 1
    assert generate.labels == {"dp": "0", "phase": "mixed", "role": "mixed"}
    assert any(sample.value != sample.value for sample in samples if sample.name == "optional_nan")


def test_expectation_supports_fallback_names_labels_and_rules(tmp_path):
    report = assert_metric_expectations(
        PROMETHEUS_TEXT,
        [
            MetricExpectation(
                names=["old_name", "vllm_profiling_engine:generate:duration_count"],
                rules=["exists", "finite", "gt:0"],
                labels={"dp": "present", "phase": ["mixed", "decode"]},
            )
        ],
        report_path=tmp_path / "assertion_report.json",
    )

    assert len(report.passed) == 1
    assert (tmp_path / "assertion_report.json").exists()


def test_histogram_requires_count_and_sum():
    assert_metric_expectations(
        PROMETHEUS_TEXT,
        [
            MetricExpectation(
                names=["vllm_profiling_engine:generate:duration"],
                histogram=True,
                rules=["exists", "finite", "gte:0"],
                labels={"dp": "0"},
            )
        ],
    )

    with pytest.raises(MetricSmokeError):
        assert_metric_expectations(
            "metric_count 1\n",
            [MetricExpectation(names=["metric"], histogram=True)],
        )


def test_optional_and_forbidden_expectations():
    report = assert_metric_expectations(
        PROMETHEUS_TEXT,
        [
            MetricExpectation(names=["missing_optional"], required=False),
            MetricExpectation(names=["must_not_exist"], forbidden=True),
        ],
    )

    assert len(report.skipped_optional) == 1
    assert len(report.passed) == 1


def test_expectation_checks_distinct_label_values():
    text = """
metric_total{dp="0"} 1
metric_total{dp="1"} 2
"""
    assert_metric_expectations(
        text,
        [
            MetricExpectation(
                names=["metric_total"],
                labels={"dp": "present"},
                min_distinct_labels={"dp": 2},
            )
        ],
    )


def test_expectation_requires_metric_increase_from_baseline():
    expectation = MetricExpectation(names=["request_count"], increase=True)

    report = assert_metric_expectations(
        "request_count 3\n",
        [expectation],
        baseline_text="request_count 2\n",
    )
    assert len(report.passed) == 1

    with pytest.raises(MetricSmokeError):
        assert_metric_expectations(
            "request_count 2\n",
            [expectation],
            baseline_text="request_count 2\n",
        )


def test_triggered_optional_metric_skips_when_not_increased():
    report = assert_metric_expectations(
        "eplb_update_count 2\n",
        [
            MetricExpectation(
                names=["eplb_update_count"],
                required=False,
                increase=True,
                triggered=True,
            )
        ],
        baseline_text="eplb_update_count 2\n",
    )

    assert len(report.skipped_optional) == 1
    assert "should increase" in report.skipped_optional[0]["reason"]


def test_metric_polling_retries_until_expectation_passes():
    samples = iter(["request_count 1\n", "request_count 2\n"])
    calls = []

    def fetcher():
        calls.append(1)
        return next(samples)

    metrics_text, report = wait_for_metric_expectations(
        fetcher=fetcher,
        expectations=[MetricExpectation(names=["request_count"], increase=True)],
        baseline_text="request_count 1\n",
        timeout=1,
        interval=0,
    )

    assert metrics_text == "request_count 2\n"
    assert len(calls) == 2
    assert len(report.passed) == 1


def test_metric_log_health_flags_only_metric_failures(tmp_path):
    service_log = """
WARNING 06-11 NIXL is not available
[ms_service_metric.symbol] ERROR Failed to apply hook for module: boom
[ms_service_metric.metrics_manager] WARNING Failed to record metric scheduler:duration: bad labels
[ms_service_metric.symbol] WARNING No target available for symbol optional.module:func
"""

    report = scan_metric_log_health(service_log)

    assert len(report.fatal) == 2
    assert len(report.warnings) == 1
    with pytest.raises(MetricSmokeError):
        assert_metric_log_health(service_log, report_path=tmp_path / "log_health_report.json")
    assert (tmp_path / "log_health_report.json").exists()


def test_scenario_registry_and_vllm_args(tmp_path):
    context = ScenarioContext(
        model_path="/model",
        devices=[0, 1],
        port=8000,
        artifact_dir=tmp_path,
    )

    basic = get_scenario("basic")
    assert basic.build_vllm_args(context) == ["--enforce-eager", "--max-model-len", "2048"]

    eplb = get_scenario("eplb")
    eplb_args = eplb.build_vllm_args(context)
    assert eplb_args[:5] == [
        "--tensor-parallel-size",
        "2",
        "--enable-expert-parallel",
        "--max-model-len",
        "4096",
    ]
    assert eplb.build_service_env(context) == {"DYNAMIC_EPLB": "true"}
    eplb_config = json.loads(eplb_args[eplb_args.index("--additional-config") + 1])
    assert eplb_config["eplb_config"]["expert_heat_collection_interval"] == 4

    custom_eplb_context = ScenarioContext(
        model_path="/model",
        devices=[0, 1],
        port=8000,
        artifact_dir=tmp_path,
        options={
            "eplb_heat_collection_interval": 8,
            "eplb_algorithm_execution_interval": 2,
            "eplb_policy_type": 1,
            "eplb_num_redundant_experts": 0,
            "eplb_max_model_len": 8192,
        },
    )
    custom_eplb_args = eplb.build_vllm_args(custom_eplb_context)
    custom_eplb_config = json.loads(custom_eplb_args[custom_eplb_args.index("--additional-config") + 1])
    assert custom_eplb_args[custom_eplb_args.index("--max-model-len") + 1] == "8192"
    assert custom_eplb_config["eplb_config"] == {
        "dynamic_eplb": True,
        "expert_heat_collection_interval": 8,
        "algorithm_execution_interval": 2,
        "eplb_policy_type": 1,
        "num_redundant_experts": 0,
    }

    dplb = get_scenario("dplb")
    assert dplb.build_vllm_args(context, ["--trust-remote-code"]) == [
        "--enforce-eager",
        "--max-model-len",
        "2048",
        "--data-parallel-size",
        "2",
        "--data-parallel-hybrid-lb",
        "--trust-remote-code",
    ]

    with pytest.raises(MetricSmokeError):
        get_scenario("unknown")


def test_scenario_expectations_cover_stable_and_triggered_metrics():
    basic_expectations = get_scenario("basic").expectations()
    eplb_expectations = get_scenario("eplb").expectations()

    assert len([item for item in basic_expectations if item.required]) == 4
    assert all(item.increase for item in basic_expectations if item.required)
    assert len([item for item in basic_expectations if item.triggered]) == 1
    assert len([item for item in eplb_expectations if item.required]) == 2
    assert len([item for item in eplb_expectations if item.triggered]) == 3


def test_explicit_devices_override_visible_devices(monkeypatch):
    monkeypatch.setenv("ASCEND_RT_VISIBLE_DEVICES", "0")

    assert _parse_visible_devices([0, 1]) == [0, 1]
    assert _parse_visible_devices([]) == [0]
