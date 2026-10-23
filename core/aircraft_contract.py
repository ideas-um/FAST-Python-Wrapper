# core/aircraft_contract.py

"""Keep Python aircraft dictionaries aligned with the public FAST contract."""

import math
import re
from copy import deepcopy


ENGINE_SPEC_NAMES = (
    "AE2100_D3",
    "AE3007A",
    "AE501D_22G",
    "Allison_250_C30G",
    "CeRAS",
    "CF34_8E5",
    "CF6_80C2_B7F",
    "ExampleTF",
    "ExampleTP",
    "GE90_115B",
    "LEAP_1A26",
    "PT6A_114A",
    "PW_123",
    "PW_127M",
    "PW_1919G",
    "PW_2037",
    "RB211_22B_02",
    "TPE331_14GR_805H",
    "Trent_970B_84",
)
AERO_METHOD_NAMES = (
    "ConstantLD",
    "DragPolar",
)
AERO_METHOD_EXPRESSIONS = {
    "ConstantLD": "@(Aircraft) AerodynamicsPkg.ConstantLD(Aircraft)",
    "DragPolar": "@(Aircraft) AerodynamicsPkg.DragPolar(Aircraft)",
}
GEOMETRY_PRESET_NAMES = (
    "DeltaCanard",
    "LargeTurbofan",
    "LargeTurboprop",
    "LM100JNominalGeometry",
    "PittsSpecial",
    "SimpleGeometry",
    "SmallDoubleAisleTurbofan",
    "SmallTurboprop",
    "Transport",
)
GEOMETRY_PRESET_EXPRESSIONS = {
    name: f"@(Aircraft) VisualizationPkg.GeometrySpecsPkg.{name}(Aircraft)"
    for name in GEOMETRY_PRESET_NAMES
}
PROP_ARCH_PRESET_TYPES = ("C", "E", "PHE", "SHE", "TE", "PE")
PROP_ARCH_CUSTOM_TYPE = "O"
PROP_ARCH_TYPES = PROP_ARCH_PRESET_TYPES + (PROP_ARCH_CUSTOM_TYPE,)
MATLAB_EXPRESSION_KEY = "_matlab_expression"
MATLAB_CELL_KEY = "_matlab_cell"
MATLAB_ROW_KEY = "_matlab_row"
MATLAB_IDENTIFIER = re.compile(r"^[A-Za-z]\w*$")
CUSTOM_PROP_ARCH_FIELDS = (
    "Arch",
    "OperUps",
    "OperDwn",
    "EtaUps",
    "EtaDwn",
    "SrcType",
    "TrnType",
)
OUTPUT_FIELDS_TO_REMOVE = (
    ("Specs", "Aero", "L_D", "Method"),
    ("Geometry", "Preset"),
    ("Mission", "ProfileFxn"),
    ("Settings", "Dir", "Size"),
)


def prepare_aircraft(aircraft):
    """Normalize InputAircraft without mutating the caller's dictionary.

    Inputs:
        aircraft: Python InputAircraft dictionary.

    Outputs:
        Deep-copied aircraft dictionary ready for MATLAB literal conversion.

    Assumptions:
        The wrapper supports FAST preset architecture labels, plus custom O
        architectures when every architecture field is fixed numeric data.
    """

    if not isinstance(aircraft, dict):
        return aircraft

    aircraft = deepcopy(aircraft)
    aircraft.pop("Mission", None)
    propulsion = _get_propulsion_section(aircraft)

    if propulsion is None:
        return aircraft

    prop_arch = propulsion.get("PropArch")

    if not isinstance(prop_arch, dict):
        return aircraft

    arch_type = prop_arch.get("Type")

    if not isinstance(arch_type, str):
        return aircraft

    arch_type = arch_type.upper()
    if arch_type == PROP_ARCH_CUSTOM_TYPE:
        _prepare_custom_prop_arch(propulsion)
    else:
        propulsion["PropArch"] = {"Type": arch_type}

    _prepare_power_defaults(aircraft)
    _prepare_aero_method(aircraft)
    _prepare_geometry_preset(aircraft)
    _prepare_engine_spec(propulsion)

    return aircraft


def extract_mission_profile(mission):
    """Return the mission profile from a separate Mission dictionary.

    Inputs:
        mission: Python Mission dictionary containing Profile.

    Outputs:
        Mission.Profile dictionary passed into FAST's mission_profile handle.
    """

    try:
        profile = mission["Profile"]
    except (KeyError, TypeError) as error:
        raise ValueError("Mission input must include Mission.Profile for FAST runs.") from error

    if not isinstance(profile, dict):
        raise ValueError("Mission.Profile must be an object.")

    profile = deepcopy(profile)

    for field_name in ("LamDwnBySegment", "LamUpsBySegment"):
        if field_name not in profile:
            continue

        histories = profile[field_name]
        _require_segment_histories(histories, f"Mission.Profile.{field_name}")
        profile[field_name] = {
            MATLAB_CELL_KEY: histories,
        }

    return profile


def clean_output_fields(output):
    """Remove FAST runtime fields from reusable OutputAircraft data.

    Inputs:
        output: Python dictionary converted from MATLAB OutputAircraft.

    Side effects:
        Mutates output in place. The result is the public OutputAircraft dict
        returned by FAST_Python_Wrapper() and used by the JSON fixtures.
    """

    for path in OUTPUT_FIELDS_TO_REMOVE:
        current = _nested_dict(output, path[:-1])

        if isinstance(current, dict):
            current.pop(path[-1], None)

    _clean_prop_arch_fields(output)


def _get_propulsion_section(aircraft):
    """Return Specs.Propulsion when the input has that nested object."""

    try:
        propulsion = aircraft["Specs"]["Propulsion"]
    except KeyError:
        return None

    if isinstance(propulsion, dict):
        return propulsion

    return None


def _prepare_custom_prop_arch(propulsion):
    """Normalize and validate fixed numeric custom architecture data.

    Optional segment operational matrices are converted to MATLAB cell arrays
    whose order maps directly to Mission.Profile.Segs.
    """

    prop_arch = propulsion.get("PropArch")

    if not isinstance(prop_arch, dict):
        raise ValueError("PropArch.Type O requires PropArch to be an object.")

    prop_arch["Type"] = PROP_ARCH_CUSTOM_TYPE

    for field_name in CUSTOM_PROP_ARCH_FIELDS:
        if field_name not in prop_arch:
            raise ValueError(f"PropArch.Type O requires PropArch.{field_name}.")

        _require_fixed_numeric_value(
            prop_arch[field_name],
            f"PropArch.{field_name}",
        )

    for field_name in ("SrcType", "TrnType"):
        value = prop_arch[field_name]
        if (
            (isinstance(value, list) or isinstance(value, tuple))
            and all(not isinstance(item, (list, tuple)) for item in value)
        ):
            prop_arch[field_name] = {
                MATLAB_ROW_KEY: list(value),
            }

    segment_fields = ("OperUpsBySegment", "OperDwnBySegment")
    present_fields = [field for field in segment_fields if field in prop_arch]

    if present_fields and len(present_fields) != len(segment_fields):
        raise ValueError(
            "PropArch.OperUpsBySegment and PropArch.OperDwnBySegment "
            "must be supplied together."
        )

    for field_name in present_fields:
        matrices = prop_arch[field_name]
        _require_segment_matrices(matrices, f"PropArch.{field_name}")
        prop_arch[field_name] = {
            MATLAB_CELL_KEY: matrices,
        }


def _prepare_engine_spec(propulsion):
    """Convert an EngineSpecsPkg function name into a MATLAB package call."""

    engine = propulsion.get("Engine")

    if engine is None or isinstance(engine, dict):
        return

    if not isinstance(engine, str):
        raise ValueError("Specs.Propulsion.Engine must be an EngineSpecsPkg name.")

    _require_matlab_identifier(engine, "Specs.Propulsion.Engine")

    propulsion["Engine"] = {
        MATLAB_EXPRESSION_KEY: f"EngineModelPkg.EngineSpecsPkg.{engine}",
    }


def _prepare_power_defaults(aircraft):
    """Provide nested power containers that current FAST assumes exist."""

    try:
        power = aircraft["Specs"]["Power"]
    except KeyError:
        return

    if isinstance(power, dict) and "SLS" not in power:
        power.setdefault("P_W", {})


def _prepare_aero_method(aircraft):
    """Convert explicit public Aero.L_D.Method names into FAST function handles."""

    try:
        l_d = aircraft["Specs"]["Aero"]["L_D"]
    except KeyError:
        return

    if not isinstance(l_d, dict):
        return

    method = l_d.get("Method")

    if isinstance(method, dict):
        return

    if method is None:
        method = "ConstantLD"

    if not isinstance(method, str):
        raise ValueError("Specs.Aero.L_D.Method must be an aerodynamic method name.")

    if method in AERO_METHOD_EXPRESSIONS:
        expression = AERO_METHOD_EXPRESSIONS[method]
    else:
        _require_matlab_identifier(method, "Specs.Aero.L_D.Method")
        expression = f"@(Aircraft) AerodynamicsPkg.{method}(Aircraft)"

    l_d["Method"] = {
        MATLAB_EXPRESSION_KEY: expression,
    }


def _prepare_geometry_preset(aircraft):
    """Convert public Geometry.Preset names into FAST visualization handles."""

    geometry = aircraft.get("Geometry")

    if not isinstance(geometry, dict):
        return

    preset = geometry.get("Preset")

    if preset is None or isinstance(preset, dict):
        return

    if not isinstance(preset, str):
        raise ValueError("Geometry.Preset must be a geometry preset name.")

    if preset in GEOMETRY_PRESET_EXPRESSIONS:
        expression = GEOMETRY_PRESET_EXPRESSIONS[preset]
    else:
        _require_matlab_identifier(preset, "Geometry.Preset")
        expression = f"@(Aircraft) VisualizationPkg.GeometrySpecsPkg.{preset}(Aircraft)"

    geometry["Preset"] = {
        MATLAB_EXPRESSION_KEY: expression,
    }


def _require_fixed_numeric_value(value, label):
    """Reject values FAST cannot receive as fixed data or MATLAB expressions."""

    if isinstance(value, dict) and set(value.keys()) == {MATLAB_EXPRESSION_KEY}:
        if not isinstance(value[MATLAB_EXPRESSION_KEY], str):
            raise ValueError(f"{label} MATLAB expression must be a string.")

        return

    if isinstance(value, bool):
        raise ValueError(f"{label} must contain only fixed numeric values.")

    if isinstance(value, int) or isinstance(value, float):
        return

    if isinstance(value, list) or isinstance(value, tuple):
        for index, item in enumerate(value):
            _require_fixed_numeric_value(item, f"{label}[{index}]")

        return

    raise ValueError(f"{label} must contain only fixed numeric values.")


def _require_segment_histories(value, label):
    """Require a nonempty list of rectangular finite numeric matrices."""

    if (not isinstance(value, list) and not isinstance(value, tuple)) or not value:
        raise ValueError(f"{label} must be a nonempty list of numeric matrices.")

    for segment_index, matrix in enumerate(value):
        matrix_label = f"{label}[{segment_index}]"
        _require_numeric_matrix(matrix, matrix_label, require_square=False)


def _require_segment_matrices(value, label):
    """Require a nonempty ordered list of fixed numeric square matrices."""

    if (not isinstance(value, list) and not isinstance(value, tuple)) or not value:
        raise ValueError(f"{label} must be a nonempty list of numeric matrices.")

    for segment_index, matrix in enumerate(value):
        matrix_label = f"{label}[{segment_index}]"
        _require_numeric_matrix(matrix, matrix_label, require_square=True)


def _require_numeric_matrix(value, label, require_square):
    """Require one rectangular numeric matrix, optionally square."""

    if (not isinstance(value, list) and not isinstance(value, tuple)) or not value:
        raise ValueError(f"{label} must be a numeric matrix.")

    row_length = None
    for row_index, row in enumerate(value):
        if (not isinstance(row, list) and not isinstance(row, tuple)) or not row:
            raise ValueError(f"{label}[{row_index}] must be a numeric row.")
        if row_length is None:
            row_length = len(row)
        elif len(row) != row_length:
            raise ValueError(f"{label} rows must have equal lengths.")
        for column_index, item in enumerate(row):
            item_label = f"{label}[{row_index}][{column_index}]"
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError(f"{item_label} must be a finite number.")
            if not math.isfinite(item):
                raise ValueError(f"{item_label} must be a finite number.")

    if require_square and len(value) != row_length:
        raise ValueError(f"{label} must be square.")


def _require_matlab_identifier(value, label):
    """Require a bare MATLAB function name for package shorthand fields."""

    if MATLAB_IDENTIFIER.match(value):
        return

    raise ValueError(f"{label} must be a MATLAB function name.")


def _nested_dict(value, path):
    """Return a nested dictionary or None when any step is missing."""

    current = value

    for key in path:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    if isinstance(current, dict):
        return current

    return None


def _clean_prop_arch_fields(value):
    """Keep every PropArch object limited to Type for supported architectures.

    Assumptions:
        FAST may expand propulsion architectures into internal graph-like data.
        The wrapper exposes only the public architecture label, so expanded
        fields are intentionally removed from output.
    """

    if isinstance(value, dict):
        for key, item in list(value.items()):
            if key == "PropArch" and isinstance(item, dict):
                value[key] = _public_prop_arch(item)
                continue

            _clean_prop_arch_fields(item)

        return

    if isinstance(value, list):
        for item in value:
            _clean_prop_arch_fields(item)


def _public_prop_arch(prop_arch):
    """Return the public PropArch object from expanded FAST internals."""

    arch_type = prop_arch.get("Type")

    if isinstance(arch_type, str):
        arch_type = arch_type.upper()

    if arch_type in PROP_ARCH_TYPES:
        return {
            "Type": arch_type,
        }

    return {}
