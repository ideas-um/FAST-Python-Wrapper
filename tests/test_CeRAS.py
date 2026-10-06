# tests/test_CeRAS.py

"""Run the CeRAS JSON fixture and compare FAST output."""

from tests.helpers import (
    assert_fast_model_wrapper_matches_saved_output,
    load_example_input,
)


def test_CeRAS_wrapper_output_matches_saved_json_file(
    fast_path,
    examples_path,
):
    """Check the full CeRAS aircraft output against saved OutputAircraft.json."""

    assert_fast_model_wrapper_matches_saved_output(
        name="CeRAS",
        aircraft_and_mission=load_example_input(examples_path, "CeRAS"),
        saved="CeRAS/OutputAircraft.json",
        fast_path=fast_path,
        examples_path=examples_path,
    )
