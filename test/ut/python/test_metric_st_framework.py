# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import importlib
import sys
from pathlib import Path

import pytest


ST_PYTHON_DIR = Path(__file__).resolve().parents[2] / "st" / "python"
sys.path.insert(0, str(ST_PYTHON_DIR))

metric_assertions = importlib.import_module("metric.metric_assertions")
metric_scenarios = importlib.import_module("metric.metric_scenarios")
metric_smoke_utils = importlib.import_module("metric.metric_smoke_utils")

MetricExpectation = metric_assertions.MetricExpectation
assert_metric_expectations = metric_assertions.assert_metric_expectations
parse_prometheus_text = metric_assertions.parse_prometheus_text
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


def test_explicit_devices_override_visible_devices(monkeypatch):
    monkeypatch.setenv("ASCEND_RT_VISIBLE_DEVICES", "0")

    assert _parse_visible_devices([0, 1]) == [0, 1]
    assert _parse_visible_devices([]) == [0]
