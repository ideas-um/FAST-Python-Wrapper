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


def test_erj175lr_matches_published_conventional_baseline(
    fast_path,
    examples_path,
):
    """Keep the wrapper fixture within the published 0.5 percent accuracy."""

    from main import FAST_Python_Wrapper

    aircraft, mission = load_example_input(examples_path, "ERJ175LR")
    result = FAST_Python_Wrapper(aircraft, mission, fast_path)

    assert result["status"] == "Yes", result["log"]
    assert result["fast_main_attempted"] is True

    weight = result["output"]["Specs"]["Weight"]
    references = {
        "MTOW": 38637,
        "OEW": 21545,
        "Fuel": 9398,
    }

    for name, reference in references.items():
        relative_error = abs(weight[name] - reference) / reference
        assert relative_error <= 0.005, (
            f"{name} differs from the published baseline by "
            f"{100 * relative_error:.3f} percent"
        )
