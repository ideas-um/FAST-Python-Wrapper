# tests/test_aircraft_examples.py

"""Run aircraft JSON fixtures and compare FAST output."""

import pytest

from tests.helpers import (
    assert_fast_model_wrapper_matches_saved_output,
    load_example_input,
)


@pytest.mark.parametrize(
    "case_name",
    [
        "ATR42",
        "B777300ER",
        "CeRAS",
        "ERJ175LR",
    ],
)
def test_aircraft_wrapper_output_matches_saved_json_file(
    case_name,
    fast_path,
    examples_path,
):
    """Check each aircraft output against its saved OutputAircraft.json."""

    assert_fast_model_wrapper_matches_saved_output(
        name=case_name,
        aircraft_and_mission=load_example_input(examples_path, case_name),
        saved=f"{case_name}/OutputAircraft.json",
        fast_path=fast_path,
        examples_path=examples_path,
    )
