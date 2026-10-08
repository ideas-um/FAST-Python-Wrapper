# core/output_structure.py

"""Build and print readable OutputAircraft structure views."""

from .json_io import build_json_data
from .schema_builder import (
    apply_output_prop_arch_schema_contract,
    build_json_schema_from_value,
)
from .schema_validation import (
    is_json_schema_document,
)


def build_output_aircraft_structure(value):
    """Return a JSON Schema document for a FAST output value.

    Inputs:
        value: Python data converted from the MATLAB OutputAircraft struct.

    Outputs:
        Draft 2020-12 JSON Schema document that preserves struct field names
        and JSON value shapes.

    Assumptions:
        FAST output array lengths vary by aircraft and mission, so the schema
        validates item shape without locking one example's exact lengths.
        PropArch is post-processed to the public Type contract even when FAST
        returns internal architecture expansion fields.
    """

    schema = {
        "title": "FAST Output Aircraft Schema",
        "description": "Schema for FAST output aircraft.",
    }
    schema.update(
        build_json_schema_from_value(
            build_json_data(value),
            require_properties=True,
            require_lengths=False,
        )
    )
    return apply_output_prop_arch_schema_contract(schema)


def print_output_aircraft_structure(
    value,
    name="OutputAircraft",
    indent=0,
    depth=0,
    max_depth=None,
    max_items=None,
):
    """Print the recursive OutputAircraft structure tree.

    Inputs:
        value: JSON Schema document from build_output_aircraft_structure().
        name: Current field label to print.
        indent: Number of leading spaces for nested fields.
        depth: Current recursion depth.
        max_depth: Optional maximum recursion depth for console output.
        max_items: Optional maximum fields printed per dictionary.

    Outputs:
        None. The tree is printed to standard output.

    Side effects:
        Writes a compact structure view to the console for interactive runs.
    """

    if is_json_schema_document(value):
        value = _schema_without_document_metadata(value)

    value = unwrap_printable_schema(value)
    prefix = " " * indent

    if max_depth is not None and depth >= max_depth:
        _print_depth_limited_node(prefix, name, value)
        return

    if _is_array_schema(value):
        _print_array_schema(value, name, indent, depth, max_depth, max_items)
        return

    if _is_object_schema(value):
        _print_object_schema(value, name, indent, depth, max_depth, max_items)
        return

    if isinstance(value, dict):
        _print_plain_mapping(value, name, indent, depth, max_depth, max_items)
        return

    print(f"{prefix}{name}: {value}")


def unwrap_printable_schema(value):
    """Return the most useful branch of a schema for structure printing."""

    if not isinstance(value, dict):
        return value

    if "anyOf" in value and value["anyOf"]:
        for option in value["anyOf"]:
            if option.get("const") != "NaN":
                return unwrap_printable_schema(option)

    if "$ref" in value:
        return value["$ref"].split("/")[-1]

    return value


def _schema_without_document_metadata(value):
    """Remove document-level schema keys before printing a field tree."""

    return {
        key: item
        for key, item in value.items()
        if key not in ("$schema", "$defs", "title", "description")
    }


def _is_array_schema(value):
    """Return True when a schema node describes a JSON array."""

    return isinstance(value, dict) and value.get("type") == "array"


def _is_object_schema(value):
    """Return True when a schema node describes a JSON object."""

    return isinstance(value, dict) and value.get("type") == "object"


def _print_depth_limited_node(prefix, name, value):
    """Print a compact placeholder when max_depth stops recursion."""

    if _is_array_schema(value):
        print(f"{prefix}{name}: {_array_label(value)} ...")
        return

    if isinstance(value, dict):
        print(f"{prefix}{name}: object ...")
        return

    print(f"{prefix}{name}: {value}")


def _print_array_schema(value, name, indent, depth, max_depth, max_items):
    """Print an array schema and then its item schema, when present."""

    prefix = " " * indent
    print(f"{prefix}{name}: {_array_label(value)}")

    if "items" not in value:
        return

    print_output_aircraft_structure(
        value["items"],
        "[0]",
        indent + 2,
        depth + 1,
        max_depth,
        max_items,
    )


def _array_label(value):
    """Return array or array[N] for fixed-length arrays."""

    if (
        value.get("minItems") == value.get("maxItems")
        and "minItems" in value
    ):
        return f"array[{value['minItems']}]"

    return "array"


def _print_object_schema(value, name, indent, depth, max_depth, max_items):
    """Print an object schema by walking its properties."""

    prefix = " " * indent
    print(f"{prefix}{name}: object")

    _print_child_items(
        list(value.get("properties", {}).items()),
        indent + 2,
        depth + 1,
        max_depth,
        max_items,
        "JSON schema",
    )


def _print_plain_mapping(value, name, indent, depth, max_depth, max_items):
    """Print a normal dictionary that is not a JSON Schema object node."""

    prefix = " " * indent
    print(f"{prefix}{name}: object")

    _print_child_items(
        list(value.items()),
        indent + 2,
        depth + 1,
        max_depth,
        max_items,
        "JSON file",
    )


def _print_child_items(items, indent, depth, max_depth, max_items, source_label):
    """Print dictionary items with an optional max_items limit."""

    if max_items is None:
        printed_items = items
    else:
        printed_items = items[:max_items]

    for key, item in printed_items:
        print_output_aircraft_structure(
            item,
            key,
            indent,
            depth,
            max_depth,
            max_items,
        )

    if max_items is not None and len(items) > max_items:
        remaining = len(items) - max_items
        prefix = " " * indent
        print(f"{prefix}... {remaining} more fields in {source_label}")
