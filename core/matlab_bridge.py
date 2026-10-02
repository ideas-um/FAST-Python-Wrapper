# core/matlab_bridge.py

"""Translate between Python data and MATLAB Engine values for FAST."""

import re
from pathlib import Path


VALID_STRUCT_FIELD = re.compile(r"^[A-Za-z]\w*$")


def matlab_expr(value):
    """Return a marker for MATLAB expressions embedded in Python specs."""

    return {
        "_matlab_expression": value,
    }


def start_matlab(fast_path):
    """Start MATLAB Engine and add FAST packages/functions to the path.

    Inputs:
        fast_path: Validated FAST checkout containing Main.m.

    Outputs:
        A running MATLAB Engine object ready to evaluate FAST scripts.

    Side effects:
        Launches an external MATLAB process. FAST_Python_Wrapper() is
        responsible for quitting it after the run finishes or fails.
    """

    try:
        import matlab.engine
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "MATLAB Engine for Python is not installed in this environment."
        ) from error

    engine = matlab.engine.start_matlab()
    engine.addpath(engine.genpath(str(fast_path)), nargout=0)
    engine.cd(str(fast_path), nargout=0)
    return engine


def resolve_fast_path(fast_path):
    """Resolve and validate the configured FAST checkout path.

    Inputs:
        fast_path: Path-like value pointing to a local FAST checkout.

    Outputs:
        Absolute Path to the checkout.

    Assumptions:
        Main.m is the stable FAST entry point used by this Python wrapper.
    """

    if not fast_path:
        raise RuntimeError("FAST path is required.")

    path = Path(fast_path).expanduser().resolve()
    _validate_fast_path(path)
    return path


def _validate_fast_path(path):
    """Check that the FAST checkout has the entry point used by this module."""

    if not path.exists() or not path.is_dir():
        raise RuntimeError(f"FAST path does not exist: {path}")

    required_paths = [path / "Main.m"]
    missing_paths = [str(item) for item in required_paths if not item.exists()]

    if missing_paths:
        joined_paths = ", ".join(missing_paths)
        raise RuntimeError(f"FAST path is missing required files: {joined_paths}")


def python_to_matlab(value):
    """Convert supported Python values into MATLAB literal source text.

    Inputs:
        value: JSON-like Python value or one of the explicit MATLAB marker
            dictionaries loaded from InputAircraft.json.

    Outputs:
        MATLAB source text safe to splice into the generated evalc script.

    Assumptions:
        This is intentionally narrow. Unsupported objects fail in Python so
        MATLAB does not receive malformed struct(...) source.
    """

    if isinstance(value, dict):
        keys = set(value)

        if keys == {"_matlab_expression"}:
            return value["_matlab_expression"]

        if keys == {"_matlab_row"}:
            return _to_matlab_row(value["_matlab_row"])

        if keys == {"_matlab_cell"}:
            return _to_matlab_cell(value["_matlab_cell"])

        fields = []

        for key, item in value.items():
            if not VALID_STRUCT_FIELD.match(key):
                raise ValueError(f"Invalid MATLAB struct field name: {key}")

            fields.append(f'"{key}", {python_to_matlab(item)}')

        if not fields:
            return "struct()"

        return f"struct({', '.join(fields)})"

    if isinstance(value, str):
        escaped_value = value.replace('"', '""')
        return f'"{escaped_value}"'

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int) or isinstance(value, float):
        if value != value:
            return "NaN"

        return repr(value)

    if value is None:
        return "[]"

    if isinstance(value, list) or isinstance(value, tuple):
        return _to_matlab_array(value)

    raise TypeError(f"Unsupported MATLAB literal value: {value!r}")


def _to_matlab_array(value):
    """Convert Python list or tuple input into a MATLAB array literal.

    Assumptions:
        One-dimensional lists are column vectors because FAST mission arrays
        align by segment row. Nested lists are matrices whose inner lists are
        MATLAB rows. The _matlab_row marker is the explicit escape hatch for
        row vectors.
    """

    if not value:
        return "[]"

    if all(isinstance(item, str) for item in value):
        rows = [python_to_matlab(item) for item in value]
        return "[" + "; ".join(rows) + "]"

    if all(not isinstance(item, list) and not isinstance(item, tuple) for item in value):
        rows = [python_to_matlab(item) for item in value]
        return "[" + "; ".join(rows) + "]"

    rows = []

    for row in value:
        if not isinstance(row, list) and not isinstance(row, tuple):
            raise TypeError("MATLAB matrix rows must all be lists or tuples.")

        rows.append(", ".join(python_to_matlab(item) for item in row))

    return "[" + "; ".join(rows) + "]"


def _to_matlab_row(value):
    """Convert a one-dimensional Python sequence into a MATLAB row vector."""

    if not value:
        return "[]"

    if any(isinstance(item, list) or isinstance(item, tuple) for item in value):
        raise TypeError("MATLAB row values must be one-dimensional.")

    return "[" + ", ".join(python_to_matlab(item) for item in value) + "]"


def _to_matlab_cell(value):
    """Convert a sequence into a MATLAB column cell array.

    The wrapper uses this internal marker for ordered per-segment matrices;
    ordinary nested JSON arrays continue to mean numeric MATLAB matrices.
    """

    if not isinstance(value, list) and not isinstance(value, tuple):
        raise TypeError("MATLAB cell values must be a list or tuple.")

    # The outer scalar cell prevents MATLAB's struct constructor from
    # expanding one input object into a struct array. MATLAB consumes that
    # wrapper and stores the inner column cell array in the field.
    return "{{" + "; ".join(python_to_matlab(item) for item in value) + "}}"


def matlab_to_python(value):
    """Convert MATLAB Engine return values into ordinary Python data.

    Outputs:
        Nested dictionaries, lists, and scalars suitable for OutputAircraft.

    Assumptions:
        MATLAB Engine exposes structs and arrays with different Python shapes
        across releases, so detection is capability-based instead of importing
        concrete matlab.* classes.
    """

    if value is None or isinstance(value, str):
        return value

    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
        return value

    if isinstance(value, dict):
        return {
            key: matlab_to_python(item)
            for key, item in value.items()
        }

    struct_fields = _matlab_struct_fields(value)

    if struct_fields is not None:
        return {
            key: matlab_to_python(value[key])
            for key in struct_fields
        }

    if isinstance(value, list) or isinstance(value, tuple):
        return _convert_sequence(value)

    if _looks_like_matlab_array(value):
        return _convert_sequence(list(value))

    return value


def _matlab_struct_fields(value):
    """Return MATLAB struct field names when value behaves like a struct."""

    if not hasattr(value, "__getitem__"):
        return None

    keys = None

    if hasattr(value, "keys"):
        try:
            keys = list(value.keys())
        except TypeError:
            keys = None

    for attribute_name in ("fieldnames", "_fieldnames"):
        if keys is not None or not hasattr(value, attribute_name):
            continue

        attribute = getattr(value, attribute_name)

        try:
            if callable(attribute):
                keys = list(attribute())
            else:
                keys = list(attribute)
        except TypeError:
            keys = None

    if keys is None:
        return None

    if not all(isinstance(key, str) for key in keys):
        return None

    return keys


def _looks_like_matlab_array(value):
    """Detect MATLAB Engine array containers without importing matlab types."""

    module_name = type(value).__module__

    return (
        (module_name == "matlab" or module_name.startswith("matlab."))
        and hasattr(value, "__iter__")
        and not isinstance(value, str)
    )


def _convert_sequence(value):
    """Recursively convert list-like values returned by MATLAB Engine.

    Assumptions:
        MATLAB scalar arrays often arrive as one-item containers. Collapsing
        those keeps scalar OutputAircraft fields as scalars in Python dicts.
    """

    items = [matlab_to_python(item) for item in value]

    if len(items) == 1 and not isinstance(items[0], dict):
        return items[0]

    return items
