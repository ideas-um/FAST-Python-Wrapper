# core/schema_builder.py

"""Build JSON Schema fragments from FAST aircraft data.

This module is only responsible for creating schema dictionaries. It does not
read schema files from disk or validate user JSON; schema_validation.py handles
those checks.
"""

import json

from .aircraft_contract import PROP_ARCH_TYPES
from .json_io import is_json_number


MATLAB_ROW_KEY = "_matlab_row"


def json_schema_number():
    """Return the FAST numeric schema."""

    return {
        "type": "number",
    }


def json_schema_prop_arch():
    """Return the public propulsion architecture schema.

    Assumptions:
        OutputAircraft exposes only the public FAST architecture label. Custom
        O matrix details are accepted by the committed input schema but are not
        preserved in reusable output data.
    """

    return {
        "type": "object",
        "properties": {
            "Type": {
                "type": "string",
                "enum": list(PROP_ARCH_TYPES),
            },
        },
        "required": [
            "Type",
        ],
        "additionalProperties": False,
    }


def apply_prop_arch_schema_contract(schema):
    """Limit every PropArch schema branch to the supported Type field.

    Inputs:
        schema: Generated JSON Schema dictionary or subtree.

    Outputs:
        The same schema object after in-place normalization.

    Side effects:
        Mutates generated schemas so historical/reference output data cannot
        reintroduce internal PropArch graph fields.
    """

    if isinstance(schema, dict):
        properties = schema.get("properties")

        if isinstance(properties, dict):
            for key, item in list(properties.items()):
                if key == "PropArch":
                    properties[key] = json_schema_prop_arch()
                else:
                    apply_prop_arch_schema_contract(item)

        if "items" in schema:
            apply_prop_arch_schema_contract(schema["items"])

        if "anyOf" in schema:
            for item in schema["anyOf"]:
                apply_prop_arch_schema_contract(item)

    if isinstance(schema, list):
        for item in schema:
            apply_prop_arch_schema_contract(item)

    return schema


def build_json_schema_from_value(
    value,
    require_properties=False,
    require_lengths=False,
):
    """Infer a JSON Schema subtree from a JSON-safe FAST value.

    Inputs:
        value: Parsed or generated JSON value.
        require_properties: Whether object properties present in value should be
            listed as required in the schema.
        require_lengths: Whether observed list lengths should become minItems
            and maxItems constraints.

    Outputs:
        A JSON Schema subtree using standard Draft 2020-12 keywords.

    Assumptions:
        FAST arrays can mix finite values with non-finite string markers, so
        item schemas are merged across observed items. The string "NaN" is
        treated as FAST's numeric unspecified marker during wrapper input
        normalization.
    """

    if isinstance(value, dict):
        return _schema_from_object(value, require_properties, require_lengths)

    if isinstance(value, list):
        return _schema_from_array(value, require_properties, require_lengths)

    return _schema_from_scalar(value)


def _schema_from_object(value, require_properties, require_lengths):
    """Build the schema for a JSON object or wrapper marker."""

    keys = set(value.keys())

    if keys == {MATLAB_ROW_KEY}:
        return _schema_from_matlab_row(value, require_properties, require_lengths)

    properties = {
        key: build_json_schema_from_value(
            item,
            require_properties,
            require_lengths,
        )
        for key, item in value.items()
    }
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }

    if require_properties and properties:
        schema["required"] = list(properties)

    return schema


def _schema_from_matlab_row(value, require_properties, require_lengths):
    """Build the schema for the explicit MATLAB row-vector marker."""

    row_value = value[MATLAB_ROW_KEY]
    row_schema = {
        "type": "array",
    }

    if isinstance(row_value, list):
        row_schema = build_json_schema_from_value(
            row_value,
            require_properties,
            require_lengths,
        )

    return {
        "type": "object",
        "properties": {
            MATLAB_ROW_KEY: row_schema,
        },
        "required": [
            MATLAB_ROW_KEY,
        ],
        "additionalProperties": False,
    }


def _schema_from_array(value, require_properties, require_lengths):
    """Build the schema for a JSON array."""

    schema = {
        "type": "array",
    }

    if require_lengths:
        schema["minItems"] = len(value)
        schema["maxItems"] = len(value)

    if value:
        item_schemas = [
            build_json_schema_from_value(
                item,
                require_properties,
                require_lengths,
            )
            for item in value
        ]
        schema["items"] = merge_json_schemas(item_schemas)

    return schema


def _schema_from_scalar(value):
    """Build the schema for a scalar JSON value."""

    if isinstance(value, bool):
        return {
            "type": "boolean",
        }

    if is_json_number(value):
        return json_schema_number()

    if value in ("NaN", "Inf", "-Inf"):
        return {
            "const": value,
        }

    if isinstance(value, str):
        return {
            "type": "string",
        }

    if value is None:
        return {
            "type": "null",
        }

    return {
        "type": "string",
    }


def merge_json_schemas(schemas):
    """Return one schema accepting each schema in a list.

    Inputs:
        schemas: JSON Schema subtrees inferred from example values.

    Outputs:
        A merged schema that keeps shared object/array structure when possible
        and falls back to anyOf only when the observed shapes truly differ.
    """

    unique_schemas = _unique_json_schemas(schemas)

    if len(unique_schemas) == 1:
        return unique_schemas[0]

    if all(schema.get("type") == "object" for schema in unique_schemas):
        return merge_json_object_schemas(unique_schemas)

    if all(schema.get("type") == "array" for schema in unique_schemas):
        return merge_json_array_schemas(unique_schemas)

    any_of = []

    for schema in unique_schemas:
        if set(schema.keys()) == {"anyOf"}:
            any_of.extend(schema["anyOf"])
        else:
            any_of.append(schema)

    return merge_json_schemas_without_specialization(any_of)


def merge_json_schemas_without_specialization(schemas):
    """Return an anyOf schema without recursively merging schema kinds.

    Assumptions:
        Mixed scalar/container observations should stay explicit so validation
        errors point at the accepted alternatives instead of a guessed shape.
    """

    unique_schemas = _unique_json_schemas(schemas)

    if len(unique_schemas) == 1:
        return unique_schemas[0]

    return {
        "anyOf": unique_schemas,
    }


def merge_json_object_schemas(schemas):
    """Merge object schemas from multiple FAST output examples."""

    property_names = []
    property_name_set = set()
    required_sets = []

    for schema in schemas:
        properties = schema.get("properties", {})

        for key in properties:
            if key not in property_name_set:
                property_names.append(key)
                property_name_set.add(key)

        required_sets.append(set(schema.get("required", [])))

    merged_properties = {}

    for key in property_names:
        child_schemas = [
            schema["properties"][key]
            for schema in schemas
            if key in schema.get("properties", {})
        ]
        merged_properties[key] = merge_json_schemas(child_schemas)

    merged_schema = {
        "type": "object",
        "properties": merged_properties,
        "additionalProperties": False,
    }

    required = [
        key
        for key in property_names
        if required_sets and all(key in required_set for required_set in required_sets)
    ]

    if required:
        merged_schema["required"] = required

    return merged_schema


def merge_json_array_schemas(schemas):
    """Merge array schemas from multiple FAST output examples."""

    item_schemas = [
        schema["items"]
        for schema in schemas
        if "items" in schema
    ]
    merged_schema = {
        "type": "array",
    }

    if item_schemas:
        merged_schema["items"] = merge_json_schemas(item_schemas)

    return merged_schema


def _unique_json_schemas(schemas):
    """Return schemas without duplicates while preserving first-seen order."""

    unique_schemas = []
    seen_schemas = set()

    for schema in schemas:
        key = json.dumps(schema, sort_keys=True)

        if key not in seen_schemas:
            unique_schemas.append(schema)
            seen_schemas.add(key)

    return unique_schemas
