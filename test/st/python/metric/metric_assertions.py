# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# -------------------------------------------------------------------------
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from metric.metric_smoke_utils import MetricSmokeError


SAMPLE_RE = re.compile(
    r"^(?P<name>[^\s{]+)(?:\{(?P<labels>[^}]*)\})?\s+"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[-+]?Inf|NaN)$"
)


@dataclass
class MetricSample:
    name: str
    labels: dict[str, str]
    value: float
    raw: str


@dataclass
class MetricExpectation:
    names: list[str]
    required: bool = True
    forbidden: bool = False
    histogram: bool = False
    rules: list[str] = field(default_factory=lambda: ["exists"])
    labels: dict[str, object] = field(default_factory=dict)
    min_distinct_labels: dict[str, int] = field(default_factory=dict)
    description: str = ""


@dataclass
class AssertionReport:
    passed: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    skipped_optional: list[dict] = field(default_factory=list)

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.__dict__, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )

    def summary(self) -> str:
        lines = [
            "[metric-assertions] "
            f"passed={len(self.passed)}, "
            f"optional_skipped={len(self.skipped_optional)}, "
            f"failed={len(self.failed)}"
        ]
        for item in self.passed:
            desc = item["expectation"].get("description") or ",".join(item["expectation"].get("names", []))
            matched = item.get("matched") or ["<no sample>"]
            lines.append(f"[metric-assertions] PASS {desc}: {matched[0]}")
        for item in self.skipped_optional:
            desc = item["expectation"].get("description") or ",".join(item["expectation"].get("names", []))
            lines.append(f"[metric-assertions] OPTIONAL-SKIP {desc}")
        for item in self.failed:
            desc = item["expectation"].get("description") or ",".join(item["expectation"].get("names", []))
            lines.append(f"[metric-assertions] FAIL {desc}: {item.get('reason')}")
        return "\n".join(lines)


def parse_prometheus_text(metrics_text: str) -> list[MetricSample]:
    samples = []
    for raw in metrics_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = SAMPLE_RE.match(line)
        if not match:
            continue
        samples.append(
            MetricSample(
                name=match.group("name"),
                labels=_parse_labels(match.group("labels") or ""),
                value=_parse_float(match.group("value")),
                raw=line,
            )
        )
    return samples


def assert_metric_expectations(
    metrics_text: str,
    expectations: list[MetricExpectation],
    report_path: Optional[Path] = None,
) -> AssertionReport:
    samples = parse_prometheus_text(metrics_text)
    report = AssertionReport()

    for expectation in expectations:
        matched = _find_matches(samples, expectation)

        if expectation.forbidden:
            if matched:
                report.failed.append(_failure(expectation, "forbidden metric was present", matched, samples))
            else:
                report.passed.append(_success(expectation, []))
            continue

        if not matched:
            if expectation.required:
                report.failed.append(_failure(expectation, "required metric was not found", [], samples))
            else:
                report.skipped_optional.append(_success(expectation, []))
            continue

        rule_error = _check_rules(expectation.rules, matched)
        if not rule_error:
            rule_error = _check_distinct_labels(expectation.min_distinct_labels, matched)
        if rule_error:
            report.failed.append(_failure(expectation, rule_error, matched, samples))
        else:
            report.passed.append(_success(expectation, matched))

    if report_path:
        report.write(report_path)

    print(report.summary())

    if report.failed:
        raise MetricSmokeError(json.dumps(report.failed, ensure_ascii=False, indent=2, default=_json_default))
    return report


def _parse_labels(raw_labels: str) -> dict[str, str]:
    labels = {}
    if not raw_labels:
        return labels
    for item in re.finditer(r'([^=,]+)="((?:\\.|[^"])*)"', raw_labels):
        labels[item.group(1)] = item.group(2).replace(r"\"", '"')
    return labels


def _parse_float(raw_value: str) -> float:
    lowered = raw_value.lower()
    if lowered == "nan":
        return math.nan
    if lowered in ("+inf", "inf"):
        return math.inf
    if lowered == "-inf":
        return -math.inf
    return float(raw_value)


def _labels_match(actual: dict[str, str], expected: dict[str, object]) -> bool:
    for key, rule in expected.items():
        if rule == "present":
            if key not in actual:
                return False
        elif isinstance(rule, (list, tuple, set)):
            if actual.get(key) not in {str(value) for value in rule}:
                return False
        elif actual.get(key) != str(rule):
            return False
    return True


def _check_rules(rules: list[str], samples: list[MetricSample]) -> Optional[str]:
    values = [sample.value for sample in samples]
    for rule in rules:
        if rule == "exists":
            continue
        if rule == "finite" and not all(math.isfinite(value) for value in values):
            return "metric value should be finite"
        if rule == "gt:0" and not any(value > 0 for value in values):
            return "metric value should have at least one sample > 0"
        if rule == "gte:0" and not all(value >= 0 for value in values):
            return "metric values should be >= 0"
    return None


def _find_matches(samples: list[MetricSample], expectation: MetricExpectation) -> list[MetricSample]:
    if not expectation.histogram:
        matched = [sample for sample in samples if sample.name in expectation.names]
        return [sample for sample in matched if _labels_match(sample.labels, expectation.labels)]

    for base_name in expectation.names:
        count_samples = [
            sample
            for sample in samples
            if sample.name == f"{base_name}_count" and _labels_match(sample.labels, expectation.labels)
        ]
        sum_samples = [
            sample
            for sample in samples
            if sample.name == f"{base_name}_sum" and _labels_match(sample.labels, expectation.labels)
        ]
        if count_samples and sum_samples:
            return [*count_samples, *sum_samples]
    return []


def _check_distinct_labels(
    requirements: dict[str, int],
    samples: list[MetricSample],
) -> Optional[str]:
    for label_name, minimum in requirements.items():
        values = {sample.labels[label_name] for sample in samples if label_name in sample.labels}
        if len(values) < minimum:
            return f"label '{label_name}' should have at least {minimum} distinct values, got {sorted(values)}"
    return None


def _failure(
    expectation: MetricExpectation,
    reason: str,
    matched: list[MetricSample],
    samples: list[MetricSample],
) -> dict:
    prefixes = {_metric_prefix(name) for name in expectation.names}
    candidates = [sample.raw for sample in samples if any(sample.name.startswith(prefix) for prefix in prefixes)][:50]
    return {
        "expectation": expectation.__dict__,
        "reason": reason,
        "matched": [sample.raw for sample in matched][:20],
        "candidates": candidates,
    }


def _success(expectation: MetricExpectation, matched: list[MetricSample]) -> dict:
    return {
        "expectation": expectation.__dict__,
        "matched": [sample.raw for sample in matched[:5]],
    }


def _metric_prefix(name: str) -> str:
    parts = name.split(":")
    if len(parts) >= 2:
        return ":".join(parts[:2])
    return name.rsplit("_", 1)[0]


def _json_default(value):
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
