"""Publication must honor the documented global gate and every critical gate."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "coverage_gate", Path(__file__).resolve().parents[2] / "qa/check_coverage.py"
)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


@pytest.fixture
def report():
    return {
        "totals": {"percent_covered": 66.91},
        "files": {
            name: {"summary": {"percent_covered": minimum}}
            for name, minimum in gate.CRITICAL.items()
        },
    }


def test_documented_global_threshold_is_consistent():
    root = Path(__file__).resolve().parents[2]
    assert gate.GLOBAL_MINIMUM == 50
    for name in ("TESTES_AUTOMATIZADOS.md", "CI_CD.md"):
        assert "50%" in (root / "docs" / name).read_text(encoding="utf-8")


def test_global_coverage_does_not_replace_critical_coverage(report):
    assert gate.coverage_failures(report) == []
    report["totals"]["percent_covered"] = 49.99
    assert gate.coverage_failures(report) == ["Total backend coverage is below 50%"]


@pytest.mark.parametrize("filename", gate.CRITICAL)
def test_every_critical_threshold_is_enforced_independently(report, filename):
    report["totals"]["percent_covered"] = 100
    report["files"][filename]["summary"]["percent_covered"] -= 0.01
    failures = gate.coverage_failures(report)
    assert len(failures) == 1 and filename in failures[0]


@pytest.mark.parametrize("filename", gate.CRITICAL)
def test_missing_critical_coverage_blocks_publication(report, filename):
    del report["files"][filename]
    assert any(filename in failure for failure in gate.coverage_failures(report))


def test_windows_paths_are_normalized_without_losing_thresholds(report):
    windows = deepcopy(report)
    windows["files"] = {name.replace("/", "\\"): data for name, data in report["files"].items()}
    assert gate.coverage_failures(windows) == []
