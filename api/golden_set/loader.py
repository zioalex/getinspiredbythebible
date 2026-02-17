"""Load golden set test cases from YAML files."""

from pathlib import Path

import yaml

from golden_set.models import GoldenSetCase

TEST_CASES_DIR = Path(__file__).parent / "test_cases"


def load_test_cases(directory: Path | None = None) -> list[GoldenSetCase]:
    """Load all test cases from YAML files in the given directory.

    Args:
        directory: Path to directory containing YAML files.
                   Defaults to golden_set/test_cases/.

    Returns:
        List of parsed GoldenSetCase objects.
    """
    directory = directory or TEST_CASES_DIR
    cases: list[GoldenSetCase] = []

    for yaml_file in sorted(directory.glob("*.yaml")):
        file_cases = load_test_cases_from_file(yaml_file)
        cases.extend(file_cases)

    return cases


def load_test_cases_from_file(file_path: Path) -> list[GoldenSetCase]:
    """Load test cases from a single YAML file.

    Args:
        file_path: Path to a YAML file.

    Returns:
        List of parsed GoldenSetCase objects.
    """
    with open(file_path) as f:
        data = yaml.safe_load(f)

    if not data or "cases" not in data:
        return []

    category = data.get("category", file_path.stem)
    cases = []

    for case_data in data["cases"]:
        if "category" not in case_data:
            case_data["category"] = category
        cases.append(GoldenSetCase(**case_data))

    return cases


def get_case_ids(cases: list[GoldenSetCase]) -> list[str]:
    """Extract all case IDs from a list of test cases."""
    return [c.id for c in cases]


def filter_by_category(cases: list[GoldenSetCase], category: str) -> list[GoldenSetCase]:
    """Filter test cases by category."""
    return [c for c in cases if c.category == category]


def filter_by_tags(cases: list[GoldenSetCase], tags: list[str]) -> list[GoldenSetCase]:
    """Filter test cases that have any of the given tags."""
    tag_set = set(tags)
    return [c for c in cases if tag_set.intersection(c.tags)]
