# tests/test_triet_phe_replay.py

"""Stress the triet pointwise supplied-lambda interface through Python."""

from copy import deepcopy
from math import isfinite

import pytest

from main import FAST_Python_Wrapper
from tests.helpers import load_example_input


AIRCRAFT_CASES = (
    "ATR42",
    "B777300ER",
    "CeRAS",
    "ERJ175LR",
)
POINT_SETTINGS = {
    "ATR42": (4, 5, 6, 7),
    "B777300ER": (7, 8, 9, 10),
    "CeRAS": (10, 7, 12, 8),
    "ERJ175LR": (13, 11, 9, 7),
}


def test_custom_o_segment_matrices_reproduce_conventional_aircraft(
    fast_path,
    examples_path,
):
    """Run wrapper-created custom O cells through FAST's full mission path."""

    aircraft, mission = load_example_input(examples_path, "ATR42")
    conventional = FAST_Python_Wrapper(aircraft, mission, fast_path)
    assert conventional["status"] == "Yes", conventional["log"]

    output_propulsion = conventional["output"]["Specs"]["Propulsion"]
    output_arch = output_propulsion["PropArch"]
    oper_ups, oper_dwn = _conventional_oper_matrices(
        int(output_propulsion["NumEngines"])
    )
    segment_count = len(mission["Profile"]["Segs"])
    custom_arch = {
        "Type": "O",
        "Arch": output_arch["Arch"],
        "OperUps": oper_ups,
        "OperDwn": oper_dwn,
        "OperUpsBySegment": [deepcopy(oper_ups) for _ in range(segment_count)],
        "OperDwnBySegment": [deepcopy(oper_dwn) for _ in range(segment_count)],
        "EtaUps": output_arch["EtaUps"],
        "EtaDwn": output_arch["EtaDwn"],
        "SrcType": output_arch["SrcType"],
        "TrnType": output_arch["TrnType"],
    }
    custom_aircraft = deepcopy(aircraft)
    custom_aircraft["Specs"]["Propulsion"]["NumEngines"] = int(
        output_propulsion["NumEngines"]
    )
    custom_aircraft["Specs"]["Propulsion"]["PropArch"] = custom_arch

    custom = FAST_Python_Wrapper(custom_aircraft, mission, fast_path)
    assert custom["status"] == "Yes", custom["log"]
    _assert_physical_histories_match(
        conventional["output"]["Mission"]["History"],
        custom["output"]["Mission"]["History"],
    )
    returned_arch = custom["output"]["Specs"]["Propulsion"]["PropArch"]
    assert returned_arch["OperUpsBySegment"] == custom_arch["OperUpsBySegment"]
    assert returned_arch["OperDwnBySegment"] == custom_arch["OperDwnBySegment"]


@pytest.mark.parametrize("case_name", AIRCRAFT_CASES)
def test_phe_recomputed_history_replays_exactly_with_supplied_lambda(
    case_name,
    fast_path,
    examples_path,
    tmp_path,
):
    """Replay each sized PHE mission through triet without changing physics."""

    aircraft, mission = load_example_input(examples_path, case_name)
    aircraft = _as_phe(aircraft)
    _set_mission_points(aircraft, POINT_SETTINGS[case_name])
    state_path = tmp_path / f"{case_name.lower()}_phe.mat"

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

    _assert_physical_histories_match(reference_history, replay_history)
    assert _all_finite(replay_history["SI"]["Constraints"])

    if case_name == "ATR42":
        return

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
    baseline_deficit = _as_list(
        replay_history["SI"]["Constraints"]["PowerDeficit"]
    )[takeoff_begin - 1:takeoff_end]
    takeoff_deficit = _as_list(power_deficit)[takeoff_begin - 1:takeoff_end]
    assert max(takeoff_deficit) > max(baseline_deficit) + 1.0e-6
    assert all(isfinite(value) for value in takeoff_deficit)

    if case_name == "ERJ175LR":
        _assert_malformed_histories_fail(
            supplied_aircraft,
            supplied_mission,
            fast_path,
            state_path,
        )


def _as_phe(aircraft):
    """Apply shared PHE electrical assumptions to one conventional fixture."""

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


def _set_mission_points(aircraft, values):
    """Exercise nondefault and unequal discretization counts by segment type."""

    settings = aircraft["Settings"]
    for field_name, value in zip(
        ("TkoPoints", "ClbPoints", "CrsPoints", "DesPoints"),
        values,
    ):
        settings[field_name] = value


def _conventional_oper_matrices(engine_count):
    """Build FAST's numeric conventional matrices for a custom O replay."""

    component_count = 2 * engine_count + 2
    oper_ups = [
        [0 for _ in range(component_count)]
        for _ in range(component_count)
    ]
    oper_dwn = deepcopy(oper_ups)
    sink_index = component_count - 1

    for engine_index in range(engine_count):
        engine_component = 1 + engine_index
        propulsor_component = 1 + engine_count + engine_index
        oper_ups[0][engine_component] = 1 / engine_count
        oper_ups[engine_component][propulsor_component] = 1
        oper_ups[propulsor_component][sink_index] = 1
        oper_dwn[engine_component][0] = 1
        oper_dwn[propulsor_component][engine_component] = 1
        oper_dwn[sink_index][propulsor_component] = 1 / engine_count

    return oper_ups, oper_dwn


def _assert_physical_histories_match(reference, replay):
    """Compare every history field except mode-specific constraint residuals."""

    for unit_system in ("SI", "EE"):
        reference_units = deepcopy(reference[unit_system])
        replay_units = deepcopy(replay[unit_system])
        reference_units.pop("Constraints")
        replay_units.pop("Constraints")
        assert reference_units == replay_units

    assert reference["Segment"] == replay["Segment"]
    assert reference.get("Flags") == replay.get("Flags")


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
    for split_history, begin, end in zip(
        mission["Profile"]["LamDwnBySegment"],
        segment_begin,
        segment_end,
    ):
        assert len(split_history) == int(end) - int(begin) + 1
    return mission


def _assert_malformed_histories_fail(aircraft, mission, fast_path, state_path):
    """Confirm FAST rejects bad segment count, point count, and split width."""

    bad_segment_count = deepcopy(mission)
    bad_segment_count["Profile"]["LamDwnBySegment"].pop()
    _assert_fast_rejects(
        aircraft,
        bad_segment_count,
        fast_path,
        state_path,
        "one entry per mission segment",
    )

    bad_point_count = deepcopy(mission)
    bad_point_count["Profile"]["LamDwnBySegment"][0].pop()
    _assert_fast_rejects(
        aircraft,
        bad_point_count,
        fast_path,
        state_path,
        "must be a finite numeric",
    )

    bad_split_width = deepcopy(mission)
    bad_split_width["Profile"]["LamDwnBySegment"][0] = [
        row + [row[0]]
        for row in bad_split_width["Profile"]["LamDwnBySegment"][0]
    ]
    _assert_fast_rejects(
        aircraft,
        bad_split_width,
        fast_path,
        state_path,
        "must be a finite numeric",
    )

    bad_mode = deepcopy(aircraft)
    bad_mode["Settings"]["PowerManagement"]["Mode"] = "UnknownMode"
    _assert_fast_rejects(
        bad_mode,
        mission,
        fast_path,
        state_path,
        "PowerManagement.Mode",
    )


def _assert_fast_rejects(aircraft, mission, fast_path, state_path, message):
    """Require one malformed wrapper call to fail with a useful FAST message."""

    result = FAST_Python_Wrapper(
        aircraft,
        mission,
        fast_path,
        state_input_path=state_path,
    )
    assert result["status"] == "No"
    assert result["output"] == {}
    assert message in result["log"]


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
