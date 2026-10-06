# tests/helpers.py

"""Helpers for comparing Python wrapper output and saved FAST JSON results.

The tests intentionally run MATLAB instead of mocking it. The wrapper exists
to preserve FAST behavior from Python-defined inputs, so the useful regression
boundary is the final FAST aircraft structure rather than isolated helper
methods.
"""

import importlib.util
import math
import os
import pytest
import shutil
from pathlib import Path

from core.json_io import (
    build_json_data,
    is_json_number,
    read_raw_json_file,
)
from main import FAST_Python_Wrapper


PROJECT_ROOT = Path(__file__).resolve().parents[1]

IGNORED_OUTPUT_PATHS = {
    "Aircraft.Settings.Dir.Oper",
    "Aircraft.Settings.Dir.Size",
    "Aircraft.Settings.Plotting",
}


def skip_unless_matlab_available():
    """Skip integration tests when MATLAB or MATLAB Engine is unavailable.

    Side effects:
        Calls pytest.skip() before any expensive FAST setup when local MATLAB
        requirements are missing.
    """

    if shutil.which("matlab") is None:
        pytest.skip("MATLAB executable is not available on PATH.")

    try:
        matlab_engine_spec = importlib.util.find_spec("matlab.engine")
    except ModuleNotFoundError:
        matlab_engine_spec = None

    if matlab_engine_spec is None:
        pytest.skip("MATLAB Engine for Python is not installed.")


@pytest.fixture
def fast_path():
    """Return the configured FAST checkout path for integration tests.

    Inputs:
        FAST_PATH environment variable.

    Outputs:
        Absolute Path to a local FAST checkout.
    """

    skip_unless_matlab_available()
    value = os.environ.get("FAST_PATH", "").strip()

    if not value or r"\path\to\\" in value or r"\path\to" in value:
        pytest.skip("Set FAST_PATH to a local FAST checkout to run integration tests.")

    return Path(value).resolve()


@pytest.fixture
def examples_path():
    """Return the root examples path used by parity tests.

    Side effects:
        None.
    """

    return PROJECT_ROOT / "examples"


def load_example_input(examples_path, case_path):
    """Load example aircraft and mission JSON input fixtures.

    Inputs:
        examples_path: Root path for examples.
        case_path: Case directory name, such as ATR42.

    Outputs:
        Pair of Python dictionaries accepted by FAST_Python_Wrapper().

    Assumptions:
        These fixture files intentionally mirror historical FAST MATLAB input
        functions, including marker objects for NaN, MATLAB expressions, and
        row vectors where MATLAB orientation matters.
    """

    aircraft_path = examples_path / case_path / "InputAircraft.json"
    mission_path = examples_path / case_path / "Mission.json"
    return (
        read_raw_json_file(aircraft_path),
        read_raw_json_file(mission_path),
    )


def compare_json_value(actual, expected, path="Aircraft"):
    """Return recursive JSON comparison failures.

    Inputs:
        actual: JSON-safe output from FAST_Python_Wrapper().
        expected: Saved JSON fixture output.
        path: Dotted path used in failure messages.

    Outputs:
        A tuple of failure messages and scalar/container values compared.

    Assumptions:
        Numeric FAST output can vary slightly between MATLAB runs, so numbers
        are compared with the same tolerance used by the previous MATLAB
        parity check. Machine-specific runtime fields are ignored.
    """

    if path in IGNORED_OUTPUT_PATHS:
        return [], 0

    if isinstance(actual, dict) and isinstance(expected, dict):
        failures = []
        compared = 1
        actual_keys = set(actual)
        expected_keys = set(expected)

        for key in sorted(expected_keys - actual_keys):
            failures.append(f"{path}.{key} missing from wrapper output")

        for key in sorted(actual_keys - expected_keys):
            failures.append(f"{path}.{key} missing from saved output")

        for key in sorted(actual_keys & expected_keys):
            child_failures, child_compared = compare_json_value(
                actual[key],
                expected[key],
                f"{path}.{key}",
            )
            failures.extend(child_failures)
            compared += child_compared

        return failures, compared

    if isinstance(actual, list) and isinstance(expected, list):
        failures = []
        compared = 1

        if len(actual) != len(expected):
            return [f"{path} list length mismatch: {len(actual)} != {len(expected)}"], compared

        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            child_failures, child_compared = compare_json_value(
                actual_item,
                expected_item,
                f"{path}[{index}]",
            )
            failures.extend(child_failures)
            compared += child_compared

        return failures, compared

    if is_json_number(actual) and is_json_number(expected):
        if math.isnan(actual) and math.isnan(expected):
            return [], 1

        if math.isinf(actual) or math.isinf(expected):
            if actual == expected:
                return [], 1

            return [f"{path} numeric mismatch: {actual!r} != {expected!r}"], 1

        tolerance = 5e-5 + 1e-8 * abs(expected)

        if abs(actual - expected) <= tolerance:
            return [], 1

        return [f"{path} numeric mismatch: {actual!r} != {expected!r}"], 1

    if actual == expected:
        return [], 1

    return [f"{path} value mismatch: {actual!r} != {expected!r}"], 1


def assert_fast_model_wrapper_matches_saved_output(
    name,
    aircraft_and_mission,
    saved,
    fast_path,
    examples_path,
):
    """Run one JSON fixture case through FAST_Python_Wrapper() and compare JSON output.

    Inputs:
        name: Aircraft case name used in failure output.
        aircraft_and_mission: Pair of Python dictionaries generated from the
            vendored aircraft and mission JSON input fixtures.
        saved: Case-relative path to the saved OutputAircraft.json baseline.
        fast_path: Local FAST checkout path.
        examples_path: Example fixture root.

    Outputs:
        None. Assertions fail when any comparable wrapper result field differs
        from the saved FAST output JSON field.

    Assumptions:
        The JSON fixture files provide separate aircraft and mission data for
        the run. Integration checks compare the final aircraft recursively because
        smaller mocked checks cannot prove parity with MATLAB FAST.
    """

    if not examples_path.exists():
        pytest.skip(f"examples path not found: {examples_path}")

    aircraft, mission = aircraft_and_mission
    result = FAST_Python_Wrapper(aircraft, mission, fast_path, simplify_output=True)

    assert result["status"] == "Yes", f"{name} FAST run failed:\n{result['log']}"

    actual = build_json_data(result["output"])
    expected = read_raw_json_file(examples_path / saved)
    failures, compared = compare_json_value(actual, expected)

    assert compared > 0, f"{name} did not compare any output fields"
    assert not failures, (
        f"{name} wrapper output differs from OutputAircraft.json:\n"
        + "\n".join(failures[:50])
    )
