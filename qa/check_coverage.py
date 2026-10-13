"""Gate total coverage and independently protect security-critical modules."""

import json
from pathlib import Path
import sys

from coverage import Coverage


# This release gate is defined in docs/TESTES_AUTOMATIZADOS.md and docs/CI_CD.md.
# Keep whole-application coverage separate from the higher critical-module gates.
GLOBAL_MINIMUM = 50

CRITICAL = {
    "backend/app/auth/security.py": 90,
    "backend/app/auth/dependencies.py": 85,
    "backend/app/core/security.py": 95,
    "backend/app/db/session.py": 85,
    "backend/app/crm/dashboard.py": 95,
}


def coverage_failures(report):
    failures = []
    total = report["totals"]["percent_covered"]
    print(f"Total backend coverage: {total:.2f}% (minimum {GLOBAL_MINIMUM}%)")
    if total < GLOBAL_MINIMUM:
        failures.append(f"Total backend coverage is below {GLOBAL_MINIMUM}%")
    files = {name.replace("\\", "/"): data for name, data in report["files"].items()}
    for filename, minimum in CRITICAL.items():
        value = files.get(filename, {}).get("summary", {}).get("percent_covered", 0)
        print(f"{filename}: {value:.2f}% (minimum {minimum}%)")
        if value < minimum:
            failures.append(f"{filename}: {value:.2f}% < {minimum}%")
    return failures


def main():
    reports = Path("test-results/coverage")
    reports.mkdir(parents=True, exist_ok=True)
    coverage = Coverage(data_file=".coverage", config_file="qa/coverage.ini")
    coverage.combine(data_paths=["test-results/coverage-data"], keep=True, strict=True)
    coverage.save()
    coverage.xml_report()
    coverage.html_report()
    coverage.json_report(outfile=str(reports / "coverage.json"))
    report = json.loads((reports / "coverage.json").read_text())
    failures = coverage_failures(report)
    if failures:
        sys.exit("\n".join(failures))


if __name__ == "__main__":
    main()
