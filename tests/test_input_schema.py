# tests/test_input_schema.py

"""Check committed JSON files against the aircraft and mission contracts."""

from copy import deepcopy

import pytest

from core.aircraft_contract import (
    AERO_METHOD_NAMES,
    ENGINE_SPEC_NAMES,
    GEOMETRY_PRESET_NAMES,
    prepare_aircraft,
)
from core.json_io import (
    INPUT_AIRCRAFT_SCHEMA_JSON_PATH,
    JsonValidationError,
    build_json_data,
    read_raw_json_file,
)
from core.matlab_bridge import python_to_matlab
from core.schema_validation import (
    read_schema_file,
    validate_aircraft_json,
    validate_json_schema_document,
    validate_mission_json,
    validate_output_aircraft_json,
)
from tests.helpers import PROJECT_ROOT


DEFAULT_INPUT_DIR = PROJECT_ROOT / "examples" / "ATR42"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
CASE_NAMES = [
    "ATR42",
]


def test_input_aircraft_matches_schema_contract():
    """Validate the default aircraft input template contract."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")

    validate_aircraft_json(data)


@pytest.mark.parametrize("case_name", CASE_NAMES)
def test_example_input_aircraft_matches_schema_contract(case_name):
    """Validate each example aircraft input against the wrapper contract."""

    data = read_raw_json_file(
        EXAMPLES_DIR / case_name / "InputAircraft.json"
    )

    validate_aircraft_json(data)


@pytest.mark.parametrize("case_name", CASE_NAMES)
def test_example_mission_matches_schema_contract(case_name):
    """Validate each example mission input against the wrapper contract."""

    data = read_raw_json_file(
        EXAMPLES_DIR / case_name / "Mission.json"
    )

    validate_mission_json(data)


@pytest.mark.parametrize("case_name", CASE_NAMES)
def test_example_output_aircraft_matches_schema_contract(case_name):
    """Validate each example aircraft output against the output schema."""

    data = read_raw_json_file(EXAMPLES_DIR / case_name / "OutputAircraft.json")

    validate_output_aircraft_json(data)


def test_json_data_omits_object_memory_address():
    """Keep generated opaque object strings stable across Python processes."""

    data = build_json_data(object())

    assert " at 0x" not in data


def test_json_data_serializes_nonfinite_numbers_as_strings():
    """Write non-finite FAST numbers as portable JSON string markers."""

    data = build_json_data(
        [
            float("nan"),
            float("inf"),
            -float("inf"),
        ]
    )

    assert data == [
        "NaN",
        "Inf",
        "-Inf",
    ]


def test_input_aircraft_contract_allows_fast_owned_fields():
    """Let FAST own aircraft fields the wrapper does not need to interpret."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    changed["Specs"]["Unexpected"] = {}

    validate_aircraft_json(changed)


def test_prepare_aircraft_passes_unknown_prop_arch_to_fast():
    """Let FAST decide whether a propulsion architecture label is supported."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "PropArch": {
                        "Type": "future",
                    },
                },
            },
        }
    )

    assert prepared["Specs"]["Propulsion"]["PropArch"] == {
        "Type": "FUTURE",
    }


@pytest.mark.parametrize("engine_name", ENGINE_SPEC_NAMES)
def test_input_aircraft_contract_accepts_engine_spec_name(engine_name):
    """Accept engine names that map to FAST EngineSpecsPkg functions."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    changed["Specs"]["Propulsion"]["Engine"] = engine_name

    validate_aircraft_json(changed)


def test_prepare_aircraft_accepts_future_engine_spec_name():
    """Convert future FAST EngineSpecsPkg names without a wrapper release."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "Engine": "FutureEngine",
                    "PropArch": {
                        "Type": "C",
                    },
                },
            },
        }
    )

    matlab_source = python_to_matlab(prepared["Specs"]["Propulsion"]["Engine"])

    assert matlab_source == "EngineModelPkg.EngineSpecsPkg.FutureEngine"


def test_prepare_aircraft_converts_engine_spec_name_to_matlab_expression():
    """Convert public engine names to FAST package calls only at runtime."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "Engine": "CF34_8E5",
                    "PropArch": {
                        "Type": "C",
                    },
                },
            },
        }
    )

    matlab_source = python_to_matlab(prepared["Specs"]["Propulsion"]["Engine"])

    assert matlab_source == "EngineModelPkg.EngineSpecsPkg.CF34_8E5"


def test_prepare_aircraft_adds_missing_power_to_weight_container():
    """Provide P_W when FAST needs to fill default power-to-weight fields."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Power": {},
                "Propulsion": {
                    "PropArch": {
                        "Type": "C",
                    },
                },
            },
        }
    )

    assert prepared["Specs"]["Power"]["P_W"] == {}


@pytest.mark.parametrize("method_name", AERO_METHOD_NAMES)
def test_input_aircraft_contract_accepts_aero_method_name(method_name):
    """Accept aerodynamic method names that map to FAST AerodynamicsPkg."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    changed["Specs"]["Aero"]["L_D"]["Method"] = method_name

    validate_aircraft_json(changed)


def test_prepare_aircraft_accepts_future_aero_method_name():
    """Convert future FAST AerodynamicsPkg names without a wrapper release."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Aero": {
                    "L_D": {
                        "Method": "FutureAero",
                    },
                },
                "Propulsion": {
                    "PropArch": {
                        "Type": "C",
                    },
                },
            },
        }
    )

    matlab_source = python_to_matlab(prepared["Specs"]["Aero"]["L_D"]["Method"])

    assert matlab_source == "@(Aircraft) AerodynamicsPkg.FutureAero(Aircraft)"


def test_prepare_aircraft_converts_aero_method_name_to_matlab_expression():
    """Convert public aerodynamic method names to FAST handles at runtime."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Aero": {
                    "L_D": {
                        "Method": "DragPolar",
                    },
                },
                "Propulsion": {
                    "PropArch": {
                        "Type": "C",
                    },
                },
            },
        }
    )

    matlab_source = python_to_matlab(prepared["Specs"]["Aero"]["L_D"]["Method"])

    assert matlab_source == "@(Aircraft) AerodynamicsPkg.DragPolar(Aircraft)"


def test_prepare_aircraft_defaults_omitted_aero_method():
    """Supply FAST's expected aerodynamic function handle when Method is omitted."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")

    prepared = prepare_aircraft(data)

    matlab_source = python_to_matlab(prepared["Specs"]["Aero"]["L_D"]["Method"])

    assert matlab_source == "@(Aircraft) AerodynamicsPkg.ConstantLD(Aircraft)"


@pytest.mark.parametrize("preset_name", GEOMETRY_PRESET_NAMES)
def test_input_aircraft_contract_accepts_geometry_preset_name(preset_name):
    """Accept geometry preset names that map to FAST VisualizationPkg."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    changed["Geometry"] = {
        "Preset": preset_name,
    }

    validate_aircraft_json(changed)


def test_prepare_aircraft_accepts_future_geometry_preset_name():
    """Convert future FAST GeometrySpecsPkg names without a wrapper release."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "PropArch": {
                        "Type": "C",
                    },
                },
            },
            "Geometry": {
                "Preset": "FutureGeometry",
            },
        }
    )

    matlab_source = python_to_matlab(prepared["Geometry"]["Preset"])

    assert (
        matlab_source
        == "@(Aircraft) VisualizationPkg.GeometrySpecsPkg.FutureGeometry(Aircraft)"
    )


def test_prepare_aircraft_converts_geometry_preset_name_to_matlab_expression():
    """Convert public geometry preset names to FAST handles at runtime."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "PropArch": {
                        "Type": "C",
                    },
                },
            },
            "Geometry": {
                "Preset": "Transport",
            },
        }
    )

    matlab_source = python_to_matlab(prepared["Geometry"]["Preset"])

    assert (
        matlab_source
        == "@(Aircraft) VisualizationPkg.GeometrySpecsPkg.Transport(Aircraft)"
    )


@pytest.mark.parametrize("arch_type", ["C", "E", "PHE", "SHE", "TE", "PE"])
def test_input_aircraft_contract_accepts_fast_preset_prop_arch(arch_type):
    """Accept every preset propulsion architecture implemented by FAST."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    changed["Specs"]["Propulsion"]["PropArch"]["Type"] = arch_type

    validate_aircraft_json(changed)


@pytest.mark.parametrize("arch_type", ["phe", "she", "te", "pe"])
def test_prepare_aircraft_normalizes_fast_preset_prop_arch(arch_type):
    """Normalize FAST preset labels before converting input to MATLAB."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "PropArch": {
                        "Type": arch_type,
                    },
                    "PropArchLegacy": "drop",
                },
            },
        }
    )

    assert prepared["Specs"]["Propulsion"]["PropArch"] == {
        "Type": arch_type.upper(),
    }
    assert "PropArchLegacy" not in prepared["Specs"]["Propulsion"]


def test_input_aircraft_contract_accepts_fixed_numeric_custom_prop_arch():
    """Allow O propulsion architectures with fixed numeric matrix fields."""

    validate_json_schema_document(
        fixed_custom_prop_arch(),
        prop_arch_schema(),
        "InputAircraft.json.Specs.Propulsion.PropArch",
    )


def test_input_aircraft_contract_accepts_custom_prop_arch_expressions():
    """Allow custom FAST architectures to use explicit MATLAB expressions."""

    prop_arch = fixed_custom_prop_arch()
    prop_arch["OperUps"][0][0] = {
        "_matlab_expression": "lambda"
    }

    validate_json_schema_document(
        prop_arch,
        prop_arch_schema(),
        "InputAircraft.json.Specs.Propulsion.PropArch",
    )


def test_prepare_aircraft_preserves_fixed_numeric_custom_prop_arch():
    """Keep O architecture matrix fields for MATLAB instead of collapsing Type."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    changed["Specs"]["Propulsion"]["PropArch"] = fixed_custom_prop_arch()

    prepared = prepare_aircraft(changed)

    assert prepared["Specs"]["Propulsion"]["PropArch"] == fixed_custom_prop_arch()


def test_prepare_aircraft_converts_custom_oper_matrices_directly():
    """Send fixed O operational matrices as MATLAB arrays, not functions."""

    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "PropArch": fixed_custom_prop_arch(),
                },
            },
        }
    )

    matlab_source = python_to_matlab(prepared["Specs"]["Propulsion"]["PropArch"])

    assert '"OperUps", [1, 0; 0, 1]' in matlab_source
    assert '"OperDwn", [1, 0; 0, 1]' in matlab_source


def test_prepare_aircraft_converts_segment_oper_matrices_to_cells():
    """Send ordered segment matrices as MATLAB cell arrays for FAST indexing."""

    prop_arch = fixed_custom_prop_arch()
    prop_arch["OperUpsBySegment"] = [
        [[1, 0], [0, 1]],
        [[0.95, 0], [0, 1]],
    ]
    prop_arch["OperDwnBySegment"] = [
        [[1, 0], [0, 1]],
        [[1, 0], [0, 0.95]],
    ]

    validate_json_schema_document(
        prop_arch,
        prop_arch_schema(),
        "InputAircraft.json.Specs.Propulsion.PropArch",
    )
    prepared = prepare_aircraft(
        {
            "Specs": {
                "Propulsion": {
                    "PropArch": prop_arch,
                },
            },
        }
    )
    matlab_source = python_to_matlab(prepared["Specs"]["Propulsion"]["PropArch"])

    assert '"OperUpsBySegment", {{[1, 0; 0, 1]; [0.95, 0; 0, 1]}}' in matlab_source
    assert '"OperDwnBySegment", {{[1, 0; 0, 1]; [1, 0; 0, 0.95]}}' in matlab_source


def test_prepare_aircraft_requires_both_segment_oper_matrix_lists():
    """Reject an incomplete upstream/downstream segment matrix definition."""

    prop_arch = fixed_custom_prop_arch()
    prop_arch["OperUpsBySegment"] = [prop_arch["OperUps"]]

    with pytest.raises(ValueError, match="must be supplied together"):
        prepare_aircraft(
            {
                "Specs": {
                    "Propulsion": {
                        "PropArch": prop_arch,
                    },
                },
            }
        )


def test_prepare_aircraft_rejects_custom_prop_arch_variables():
    """Reject direct Python calls with nonnumeric values in O matrices."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    prop_arch = fixed_custom_prop_arch()
    prop_arch["OperDwn"][0][0] = "lambda"
    changed["Specs"]["Propulsion"]["PropArch"] = prop_arch

    with pytest.raises(ValueError, match="PropArch.OperDwn"):
        prepare_aircraft(changed)


def test_input_aircraft_contract_allows_missing_optional_field():
    """Allow omitted optional fields that are known in the schema."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)
    del changed["Settings"]["Table"]

    validate_aircraft_json(changed)


def test_input_aircraft_contract_allows_missing_mission():
    """Keep mission data separate from InputAircraft.json."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "InputAircraft.json")
    changed = deepcopy(data)

    changed.pop("Mission", None)
    validate_aircraft_json(changed)


def fixed_custom_prop_arch():
    """Return the minimal fixed numeric O architecture used by contract tests."""

    return {
        "Type": "O",
        "Arch": [
            [1, 0],
            [0, 1],
        ],
        "OperUps": [
            [1, 0],
            [0, 1],
        ],
        "OperDwn": [
            [1, 0],
            [0, 1],
        ],
        "EtaUps": [
            [1, 0],
            [0, 1],
        ],
        "EtaDwn": [
            [1, 0],
            [0, 1],
        ],
        "SrcType": [
            1,
        ],
        "TrnType": [
            1,
            2,
        ],
    }


def prop_arch_schema():
    """Return the committed input PropArch schema branch."""

    schema = read_schema_file(INPUT_AIRCRAFT_SCHEMA_JSON_PATH)

    return schema["properties"]["Specs"]["properties"]["Propulsion"]["properties"][
        "PropArch"
    ]


def test_mission_contract_rejects_missing_profile():
    """Require Profile in the separate Mission.json file."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "Mission.json")
    changed = deepcopy(data)
    del changed["Profile"]

    with pytest.raises(JsonValidationError, match="missing required field Profile"):
        validate_mission_json(changed)


def test_input_aircraft_contract_rejects_legacy_nan_marker():
    """Reject standalone mission NaN marker strings."""

    mission = read_raw_json_file(DEFAULT_INPUT_DIR / "Mission.json")
    changed_mission = deepcopy(mission)
    changed_mission["Profile"]["ClbRate"][0] = "NaN"

    with pytest.raises(JsonValidationError, match="ClbRate"):
        validate_mission_json(changed_mission)


def test_mission_profile_contract_rejects_mismatched_target_lengths():
    """Reject mission profiles whose target values and types do not align."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "Mission.json")
    changed = deepcopy(data)
    changed["Profile"]["Target"]["Type"].append("Dist")

    with pytest.raises(JsonValidationError, match="same length"):
        validate_mission_json(changed)


def test_mission_profile_contract_rejects_missing_segment_field():
    """Reject mission profiles that omit a committed segment array."""

    data = read_raw_json_file(DEFAULT_INPUT_DIR / "Mission.json")
    changed = deepcopy(data)
    del changed["Profile"]["VelEnd"]

    with pytest.raises(JsonValidationError, match="missing required field VelEnd"):
        validate_mission_json(changed)
