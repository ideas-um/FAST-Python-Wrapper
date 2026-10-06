# core/helper.py

"""Small file-loading helpers for FAST users."""

from pathlib import Path

from .json_io import (
    AIRCRAFT_JSON_PATH,
    DEFAULT_INPUT_DIR,
    JsonValidationError,
    MISSION_JSON_PATH,
    load_json_data,
    read_raw_json_file,
)
from .schema_validation import (
    validate_aircraft_json,
    validate_mission_json,
)


def load_input_json_files(input_dir=None):
    """Load example FAST aircraft and mission dictionaries from JSON files.

    Inputs:
        input_dir: Directory containing InputAircraft.json and Mission.json. A
            missing value uses the default example directory.

    Outputs:
        Tuple of aircraft and mission dictionaries ready for FAST_Python_Wrapper().

    Assumptions:
        InputAircraft.json and Mission.json are committed/template input files
        that users edit before calling FAST_Python_Wrapper().
    """

    if input_dir is None:
        base_path = DEFAULT_INPUT_DIR
    else:
        base_path = Path(input_dir)

    aircraft_json_path = base_path / AIRCRAFT_JSON_PATH
    mission_json_path = base_path / MISSION_JSON_PATH

    if not aircraft_json_path.exists():
        raise JsonValidationError(
            f"{aircraft_json_path} is required. Edit or restore this input file, "
            "then call FAST_Python_Wrapper()."
        )

    if not mission_json_path.exists():
        raise JsonValidationError(
            f"{mission_json_path} is required. Edit or restore this input file, "
            "then call FAST_Python_Wrapper()."
        )

    aircraft_data = read_raw_json_file(aircraft_json_path)
    mission_data = read_raw_json_file(mission_json_path)
    validate_aircraft_json(aircraft_data)
    validate_mission_json(mission_data)
    return load_json_data(aircraft_data), load_json_data(mission_data)
