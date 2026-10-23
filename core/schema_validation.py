# core/schema_validation.py

"""Validate FAST JSON files against the wrapper's schema subset.

The project uses a small, explicit part of JSON Schema. Keeping that validator
local makes errors easier to tailor for FAST users and avoids hiding important
wrapper rules inside a large third-party validator.
"""

from .json_io import (
    INPUT_AIRCRAFT_SCHEMA_JSON_PATH,
    JsonValidationError,
    OUTPUT_AIRCRAFT_SCHEMA_JSON_PATH,
    SCHEMA_DIR,
    get_json_path,
    is_json_number,
    read_raw_json_file,
    require_json_object,
)
from .schema_builder import MATLAB_ROW_KEY


def read_schema_file(file_name):
    """Read a committed JSON schema from schema/.

    Inputs:
        file_name: Schema JSON file name.

    Outputs:
        Parsed schema document.

    Side effects:
        None.
    """

    path = SCHEMA_DIR / file_name

    if not path.exists():
        raise JsonValidationError(f"{path} is required for input validation.")

    return read_raw_json_file(path)


def validate_json_schema_document(data, schema, file_name, path=""):
    """Validate parsed JSON against a committed structure schema.

    Inputs:
        data: Parsed input JSON subtree.
        schema: JSON Schema document.
        file_name: Input file label used in validation errors.
        path: Current dotted JSON path.

    Outputs:
        None. Raises JsonValidationError when the input structure drifts from
        the committed schema.

    Assumptions:
        Required fields and optional null placeholders are declared directly in
        the schema files under schema/.
    """

    if not is_json_schema_document(schema):
        raise JsonValidationError(f"{file_name} schema must be a JSON Schema document.")

    validate_json_schema_value(
        data,
        schema,
        file_name,
        path or file_name,
        schema,
    )


def is_json_schema_document(schema):
    """Return True when a value is a standard JSON Schema document."""

    return (
        isinstance(schema, dict)
        and (
            "$schema" in schema
            or "properties" in schema
            or "anyOf" in schema
            or "const" in schema
        )
    )


def validate_json_schema_value(data, schema, file_name, label, root_schema):
    """Validate one JSON value against the generated JSON Schema subset.

    Inputs:
        data: Parsed JSON value being checked.
        schema: Schema subtree for this value.
        file_name: Source file label used in error messages.
        label: Dotted path to the current value.
        root_schema: Full schema document used for local $ref resolution.

    Outputs:
        None. Raises JsonValidationError with the concrete JSON path on drift.

    Assumptions:
        The project generates and consumes a small Draft 2020-12 subset; this
        validator implements only keywords used by the committed schemas.
    """

    if isinstance(data, dict) and set(data.keys()) == {"_matlab_expression"}:
        return

    if "$ref" in schema:
        schema = _validate_ref_schema(data, schema, file_name, label, root_schema)

        if schema is None:
            return

    if "not" in schema:
        _validate_excluded_schema(data, schema, file_name, label, root_schema)

    if "const" in schema and data != schema["const"]:
        raise JsonValidationError(f"{label} must equal {schema['const']!r}.")

    if "enum" in schema and data not in schema["enum"]:
        allowed = ", ".join(repr(item) for item in schema["enum"])
        raise JsonValidationError(f"{label} must be one of: {allowed}.")

    if "anyOf" in schema:
        _validate_any_of(data, schema["anyOf"], file_name, label, root_schema)
        return

    if "type" not in schema:
        return

    errors = []

    for expected_type in _schema_type_options(schema["type"]):
        try:
            validate_json_schema_type(
                data,
                schema,
                expected_type,
                file_name,
                label,
                root_schema,
            )
            return
        except JsonValidationError as error:
            errors.append(str(error))

    if len(errors) == 1:
        raise JsonValidationError(errors[0])

    expected = ", ".join(_schema_type_options(schema["type"]))
    raise JsonValidationError(f"{label} must match type {expected}.")


def _validate_ref_schema(data, schema, file_name, label, root_schema):
    """Validate a local $ref and return sibling constraints, if any."""

    validate_json_schema_value(
        data,
        resolve_json_schema_ref(schema["$ref"], root_schema),
        file_name,
        label,
        root_schema,
    )
    remaining_schema = {
        key: value
        for key, value in schema.items()
        if key != "$ref"
    }

    if remaining_schema:
        return remaining_schema

    return None


def _validate_excluded_schema(data, schema, file_name, label, root_schema):
    """Reject values that match a schema under the not keyword."""

    try:
        validate_json_schema_value(
            data,
            schema["not"],
            file_name,
            label,
            root_schema,
        )
    except JsonValidationError:
        return

    if schema["not"].get("const") == "NaN":
        raise JsonValidationError(f"{label} is required and cannot be \"NaN\".")

    raise JsonValidationError(f"{label} must not match excluded schema.")


def _validate_any_of(data, options, file_name, label, root_schema):
    """Accept a value when it matches at least one anyOf option."""

    errors = []

    for option in options:
        try:
            validate_json_schema_value(data, option, file_name, label, root_schema)
            return
        except JsonValidationError as error:
            errors.append(str(error))

    if errors:
        if data == "NaN":
            raise JsonValidationError(f"{label} is required and cannot be \"NaN\".")

        raise JsonValidationError(f"{label} must match at least one allowed schema.")

    raise JsonValidationError(f"{label} has no allowed schema.")


def _schema_type_options(expected_types):
    """Return schema type as a list so callers can loop uniformly."""

    if isinstance(expected_types, str):
        return [
            expected_types,
        ]

    return expected_types


def resolve_json_schema_ref(ref, root_schema):
    """Resolve a local JSON Schema reference from the root document."""

    prefix = "#/$defs/"

    if not ref.startswith(prefix):
        raise JsonValidationError(f"Unsupported JSON Schema reference {ref}.")

    key = ref[len(prefix):]

    try:
        return root_schema["$defs"][key]
    except KeyError as error:
        raise JsonValidationError(f"Missing JSON Schema definition {key}.") from error


def validate_json_schema_type(data, schema, expected_type, file_name, label, root_schema):
    """Validate data against one standard JSON Schema type."""

    if expected_type == "object":
        _validate_object_schema(data, schema, file_name, label, root_schema)
        return

    if expected_type == "array":
        _validate_array_schema(data, schema, file_name, label, root_schema)
        return

    if expected_type == "number":
        _validate_number_schema(data, schema, label)
        return

    if expected_type == "integer":
        _validate_integer_schema(data, schema, label)
        return

    if expected_type == "string":
        if isinstance(data, str):
            return

        raise JsonValidationError(f"{label} must be a string.")

    if expected_type == "boolean":
        if isinstance(data, bool):
            return

        raise JsonValidationError(f"{label} must be true or false.")

    if expected_type == "null":
        if data is None:
            return

        raise JsonValidationError(f"{label} must be null.")

    raise JsonValidationError(f"{label} uses unknown JSON Schema type {expected_type}.")


def _validate_object_schema(data, schema, file_name, label, root_schema):
    """Validate JSON object fields, required keys, and child values."""

    if not isinstance(data, dict):
        raise JsonValidationError(f"{label} must be a JSON object.")

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    actual_keys = set(data)
    expected_keys = set(properties)

    if schema.get("additionalProperties") is False:
        for key in sorted(actual_keys - expected_keys):
            raise JsonValidationError(f"{label} contains unexpected field {key}.")

    for key in required:
        if key not in data:
            raise JsonValidationError(f"{label} is missing required field {key}.")

    for key in sorted(actual_keys & expected_keys):
        validate_json_schema_value(
            data[key],
            properties[key],
            file_name,
            f"{label}.{key}",
            root_schema,
        )


def _validate_array_schema(data, schema, file_name, label, root_schema):
    """Validate JSON array length and each item, when item schema exists."""

    if not isinstance(data, list):
        raise JsonValidationError(f"{label} must be a JSON array.")

    if "minItems" in schema and len(data) < schema["minItems"]:
        raise JsonValidationError(
            f"{label} must contain at least {schema['minItems']} items."
        )

    if "maxItems" in schema and len(data) > schema["maxItems"]:
        raise JsonValidationError(
            f"{label} must contain at most {schema['maxItems']} items."
        )

    item_schema = schema.get("items")

    if item_schema is None:
        return

    for index, item in enumerate(data):
        validate_json_schema_value(
            item,
            item_schema,
            file_name,
            f"{label}[{index}]",
            root_schema,
        )


def _validate_number_schema(data, schema, label):
    """Validate a JSON number and its min/max limits."""

    if is_json_number(data):
        validate_json_schema_number_limits(data, schema, label)
        return

    raise JsonValidationError(f"{label} must be a number.")


def _validate_integer_schema(data, schema, label):
    """Validate a JSON integer and its min/max limits."""

    if isinstance(data, int) and not isinstance(data, bool):
        validate_json_schema_number_limits(data, schema, label)
        return

    raise JsonValidationError(f"{label} must be an integer.")


def validate_json_schema_number_limits(data, schema, label):
    """Validate minimum and maximum constraints for JSON number schemas."""

    if "minimum" in schema and data < schema["minimum"]:
        raise JsonValidationError(f"{label} must be at least {schema['minimum']}.")

    if "maximum" in schema and data > schema["maximum"]:
        raise JsonValidationError(f"{label} must be at most {schema['maximum']}.")


def require_json_number(data, keys, file_name):
    """Validate that a required nested field is numeric."""

    value = get_json_path(data, keys, file_name)

    if is_json_number(value):
        return

    joined = ".".join(keys)
    raise JsonValidationError(f"{file_name}.{joined} must be a number.")


def require_json_string(data, keys, file_name):
    """Validate that a required nested field is a string."""

    value = get_json_path(data, keys, file_name)

    if isinstance(value, str):
        return

    joined = ".".join(keys)
    raise JsonValidationError(f"{file_name}.{joined} must be a string.")


def require_json_list(data, keys, file_name):
    """Validate that a required nested field is a list and return it."""

    value = get_json_path(data, keys, file_name)

    if isinstance(value, list):
        return value

    joined = ".".join(keys)
    raise JsonValidationError(f"{file_name}.{joined} must be a JSON array.")


def validate_json_markers(value, file_name, path=""):
    """Validate MATLAB marker objects used inside JSON files.

    Inputs:
        value: Parsed JSON subtree.
        file_name: File label used in validation errors.
        path: Current dotted JSON path.

    Outputs:
        None. Raises JsonValidationError on invalid markers.

    Assumptions:
        Marker dictionaries reserve keys beginning with "_". User data should
        not mix marker keys with normal FAST fields.
    """

    if isinstance(value, dict):
        keys = set(value.keys())
        label = path or file_name
        marker_keys = [key for key in keys if key.startswith("_")]

        if marker_keys:
            if keys == {"_matlab_expression"}:
                if not isinstance(value["_matlab_expression"], str):
                    raise JsonValidationError(
                        f"{label}._matlab_expression must be a string."
                    )
                return

            if keys == {MATLAB_ROW_KEY}:
                if not isinstance(value[MATLAB_ROW_KEY], list):
                    raise JsonValidationError(f"{label}._matlab_row must be an array.")
                validate_json_markers(
                    value[MATLAB_ROW_KEY],
                    file_name,
                    f"{label}._matlab_row",
                )
                return

            if keys == {"_matlab_cell"}:
                if not isinstance(value["_matlab_cell"], list):
                    raise JsonValidationError(f"{label}._matlab_cell must be an array.")
                validate_json_markers(
                    value["_matlab_cell"],
                    file_name,
                    f"{label}._matlab_cell",
                )
                return

            raise JsonValidationError(f"{label} contains invalid marker keys.")

        for key, item in value.items():
            child_path = key if not path else f"{path}.{key}"
            validate_json_markers(item, file_name, child_path)

        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]"
            validate_json_markers(item, file_name, child_path)


def validate_aircraft_json(data):
    """Validate wrapper-essential InputAircraft.json structure.

    FAST owns the full aircraft contract. The wrapper validates only portable
    JSON markers for aircraft data before calling Main.m.
    """

    require_json_object(data, "InputAircraft.json")
    validate_json_markers(data, "InputAircraft.json")


def validate_mission_json(data):
    """Validate wrapper-essential Mission.json structure."""

    require_json_object(data, "Mission.json")
    validate_json_markers(data, "Mission.json")

    mission_profile = get_json_path(
        data,
        ["Profile"],
        "Mission.json",
    )
    validate_mission_profile_json(mission_profile)


def validate_mission_profile_json(data):
    """Validate the Mission.Profile object in Mission.json."""

    require_json_object(data, "Mission.json.Profile")

    targets = get_json_path(
        data,
        ["Target", "Valu"],
        "Mission.json.Profile",
    )
    target_types = get_json_path(
        data,
        ["Target", "Type"],
        "Mission.json.Profile",
    )

    if not isinstance(targets, list):
        targets = [targets]

    if not isinstance(target_types, list):
        target_types = [target_types]

    if len(targets) != len(target_types):
        raise JsonValidationError(
            "Mission.json Profile Target.Valu and Target.Type "
            "must have the same length."
        )

    for index, target_type in enumerate(target_types):
        if target_type not in ("Dist", "Time"):
            raise JsonValidationError(
                "Mission.json Profile Target.Type"
                f"[{index}] must be \"Dist\" or \"Time\"."
            )

    segment_fields = [
        "Segs",
        "ID",
        "AltBeg",
        "AltEnd",
        "VelBeg",
        "VelEnd",
        "TypeBeg",
        "TypeEnd",
        "ClbRate",
    ]
    segment_lengths = {}

    for field_name in segment_fields:
        segment_lengths[field_name] = len(
            require_json_list(
                data,
                [field_name],
                "Mission.json.Profile",
            )
        )

    expected_length = segment_lengths["Segs"]

    for field_name, length in segment_lengths.items():
        if length != expected_length:
            raise JsonValidationError(
                "Mission.json Profile segment arrays must have "
                "the same length: "
                f"Segs has {expected_length}, {field_name} has {length}."
            )

    for index, segment_name in enumerate(data["Segs"]):
        if not isinstance(segment_name, str):
            raise JsonValidationError(
                "Mission.json Profile Segs"
                f"[{index}] must be a string."
            )

    for index, climb_rate in enumerate(data["ClbRate"]):
        if climb_rate is None or is_json_number(climb_rate):
            continue

        raise JsonValidationError(
            "Mission.json Profile ClbRate"
            f"[{index}] must be a number or null."
        )


def validate_output_aircraft_json(data):
    """Validate OutputAircraft.json after writing FAST output data."""

    require_json_object(data, "OutputAircraft.json")
    validate_json_markers(data, "OutputAircraft.json")
    validate_json_schema_document(
        data,
        read_schema_file(OUTPUT_AIRCRAFT_SCHEMA_JSON_PATH),
        "OutputAircraft.json",
    )

    require_json_number(data, ["Specs", "Weight", "MTOW"], "OutputAircraft.json")
    require_json_number(data, ["Specs", "Weight", "Fuel"], "OutputAircraft.json")
    require_json_number(data, ["Specs", "Aero", "S"], "OutputAircraft.json")
    require_json_string(data, ["Specs", "TLAR", "Class"], "OutputAircraft.json")
    get_json_path(data, ["Mission", "Profile"], "OutputAircraft.json")
