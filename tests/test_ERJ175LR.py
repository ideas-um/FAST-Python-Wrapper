# tests/test_ERJ175LR.py

"""Run the ERJ175LR JSON fixture and compare FAST output."""

from tests.helpers import (
    assert_fast_model_wrapper_matches_saved_output,
    load_example_input,
)


def test_ERJ175LR_wrapper_output_matches_saved_json_file(
    fast_path,
    examples_path,
):
    """Check the full ERJ175LR aircraft output against saved OutputAircraft.json."""

    assert_fast_model_wrapper_matches_saved_output(
        name="ERJ175LR",
        aircraft_and_mission=load_example_input(examples_path, "ERJ175LR"),
        saved="ERJ175LR/OutputAircraft.json",
        fast_path=fast_path,
        examples_path=examples_path,
    )
