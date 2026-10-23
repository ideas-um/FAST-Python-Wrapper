# tests/test_triet_phe_replay.py

"""Stress the triet pointwise supplied-lambda interface through Python."""

from copy import deepcopy
from math import isfinite

from main import FAST_Python_Wrapper
from tests.helpers import load_example_input


PHYSICAL_HISTORY_FIELDS = (
    "Performance",
    "Aero",
    "Propulsion",
    "Weight",
    "Power",
    "Energy",
)


def test_phe_recomputed_history_replays_exactly_with_supplied_lambda(
    fast_path,
    examples_path,
    tmp_path,
):
    """Replay a sized PHE mission through triet without changing physics."""

    aircraft, mission = load_example_input(examples_path, "ERJ175LR")
    aircraft = _as_phe(aircraft)
    state_path = tmp_path / "erj175lr_phe.mat"

    sized = FAST_Python_Wrapper(
        aircraft,
        mission,
        fast_path,
        state_output_path=state_path,
    )
    assert sized["status"] == "Yes", sized["log"]

    fixed_aircraft = deepcopy(aircraft)
    fixed_aircraft["Settings"]["Analysis"]["Type"] = -1
    recomputed = FAST_Python_Wrapper(
        fixed_aircraft,
        mission,
        fast_path,
        state_input_path=state_path,
    )
    assert recomputed["status"] == "Yes", recomputed["log"]

    supplied_mission = _with_captured_splits(mission, recomputed["output"])
    supplied_aircraft = deepcopy(fixed_aircraft)
    supplied_aircraft["Settings"]["PowerManagement"]["Mode"] = "SupplyLambda"

    supplied = FAST_Python_Wrapper(
        supplied_aircraft,
        supplied_mission,
        fast_path,
        state_input_path=state_path,
    )
    assert supplied["status"] == "Yes", supplied["log"]

    reference_history = recomputed["output"]["Mission"]["History"]
    replay_history = supplied["output"]["Mission"]["History"]

    for field_name in PHYSICAL_HISTORY_FIELDS:
        assert reference_history["SI"][field_name] == replay_history["SI"][field_name]

    assert reference_history["Segment"] == replay_history["Segment"]
    assert reference_history["Flags"] == replay_history["Flags"]
    assert _all_finite(replay_history["SI"]["Constraints"])

    invalid_mission = deepcopy(supplied_mission)
    invalid_mission["Profile"]["LamDwnBySegment"][0] = [
        [0.9 for _ in row]
        for row in invalid_mission["Profile"]["LamDwnBySegment"][0]
    ]
    invalid = FAST_Python_Wrapper(
        supplied_aircraft,
        invalid_mission,
        fast_path,
        state_input_path=state_path,
    )
    assert invalid["status"] == "Yes", invalid["log"]
    power_deficit = invalid["output"]["Mission"]["History"]["SI"]["Constraints"][
        "PowerDeficit"
    ]
    takeoff_begin = int(_as_list(invalid["output"]["Mission"]["Profile"]["SegBeg"])[0])
    takeoff_end = int(_as_list(invalid["output"]["Mission"]["Profile"]["SegEnd"])[0])
    takeoff_deficit = _as_list(power_deficit)[takeoff_begin - 1:takeoff_end]
    assert any(value > 1.0e-6 for value in takeoff_deficit)
    assert all(isfinite(value) for value in takeoff_deficit)


def _as_phe(aircraft):
    """Apply the native ERJ PHE electrical assumptions to one fixture."""

    aircraft = deepcopy(aircraft)
    specs = aircraft["Specs"]
    specs["Propulsion"]["PropArch"] = {
        "Type": "PHE",
    }
    specs["Weight"]["EM"] = 0
    specs["Weight"]["Batt"] = 0
    specs["Power"].update(
        {
            "SpecEnergy": {
                "Fuel": 12,
                "Batt": 0.25,
            },
            "LamDwn": {
                "SLS": 0.1,
                "Tko": 0.1,
                "Clb": 0,
                "Crs": 0,
                "Des": 0,
                "Lnd": 0,
            },
            "LamUps": {
                "SLS": 1,
                "Tko": 1,
                "Clb": 0,
                "Crs": 0,
                "Des": 0,
                "Lnd": 0,
            },
            "Eta": {
                "EM": 0.96,
                "EG": 0.96,
            },
            "P_W": {
                "SLS": None,
                "EM": 10,
                "EG": None,
            },
            "Battery": {
                "ParCells": None,
                "SerCells": None,
                "BegSOC": 100,
            },
        }
    )
    aircraft["Settings"]["PowerManagement"] = {
        "Mode": "RecomputeLambda",
    }
    return aircraft


def _with_captured_splits(mission, output):
    """Convert global FAST split histories into per-segment Python matrices."""

    mission = deepcopy(mission)
    profile = output["Mission"]["Profile"]
    power = output["Mission"]["History"]["SI"]["Power"]
    segment_begin = _as_list(profile["SegBeg"])
    segment_end = _as_list(profile["SegEnd"])

    mission["Profile"]["LamDwnBySegment"] = _split_by_segment(
        power["LamDwn"],
        segment_begin,
        segment_end,
    )
    mission["Profile"]["LamUpsBySegment"] = _split_by_segment(
        power["LamUps"],
        segment_begin,
        segment_end,
    )
    return mission


def _split_by_segment(history, segment_begin, segment_end):
    """Slice a MATLAB history using its one-based inclusive segment bounds."""

    matrix = _as_matrix(history)
    return [
        matrix[int(begin) - 1:int(end)]
        for begin, end in zip(segment_begin, segment_end)
    ]


def _as_matrix(value):
    """Restore the column dimension that jsonencode drops for one split."""

    if not value:
        return []
    if isinstance(value[0], list):
        return value
    return [[item] for item in value]


def _as_list(value):
    """Return MATLAB scalar or vector JSON as one Python list."""

    if isinstance(value, list):
        return value
    return [value]


def _all_finite(value):
    """Return whether every numeric leaf in a nested constraint object is finite."""

    if isinstance(value, dict):
        return all(_all_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_all_finite(item) for item in value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    return isfinite(value)
