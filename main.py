# main.py

from pathlib import Path
import json

from core.aircraft_contract import (
    clean_output_fields,
    extract_mission_profile,
    prepare_aircraft,
)
from core.matlab_bridge import (
    python_to_matlab,
    resolve_fast_path,
    start_matlab,
    matlab_to_python,
)
from core.json_io import build_json_data, normalize_json_data


def FAST_Python_Wrapper(input_aircraft, mission, fast_path, simplify_output=False):
    """Run FAST once from Python InputAircraft and Mission dictionaries.

    Inputs:
        input_aircraft: Nested aircraft dictionary without Mission.Profile.
        mission: Nested Mission dictionary containing Profile.
        fast_path: Local FAST checkout path containing Main.m.

    Outputs:
        Dictionary containing:
        - status: "Yes" when FAST returns OutputAircraft, otherwise "No".
        - log: MATLAB stdout captured during the run.
        - output: Python dictionary equivalent of FAST OutputAircraft, or an
            empty dictionary when FAST does not produce one.
        Pass simplify_output=True to remove wrapper-specific runtime fields
            used by the committed JSON fixtures.

    Side effects:
        Starts MATLAB Engine, adds FAST to the MATLAB path, runs Main.m, and
        quits MATLAB before returning.
    """
    # Start MATLAB Engine
    engine = start_matlab(resolve_fast_path(fast_path))

    if hasattr(engine, "addpath"):
        engine.addpath(str(Path(__file__).resolve().parent / "core"), nargout=0)

    try:
        try:
            # Convert Python Dictionary to MATLAB struct
            aircraft_python = prepare_aircraft(normalize_json_data(input_aircraft))
            mission_python = extract_mission_profile(normalize_json_data(mission))
            aircraft_matlab = python_to_matlab(aircraft_python)
            mission_matlab = python_to_matlab(mission_python)
        except Exception as error:
            return {
                "status": "No",
                "log": str(error),
                "output": {},
            }

        try:
            # Run FAST in MATLAB
            log = engine.evalc(
                f"""
                aircraft_spec = {aircraft_matlab};
                mission_profile = @(Aircraft) setfield(Aircraft, "Mission", "Profile", {mission_matlab});
                fast_result = struct();
                fast_result_json = '';
                fast_status = 'No';
                try
                    fast_result = Main(aircraft_spec, mission_profile);
                    fast_result_json = jsonencode(fast_json_ready(fast_result));
                    fast_status = 'Yes';
                catch fast_exception
                    disp(getReport(fast_exception, 'extended', 'hyperlinks', 'off'));
                end
                """,
                nargout=1,
            )
        except Exception as error:
            return {
                "status": "No",
                "log": str(error),
                "output": {},
            }

        try:
            # Extract FAST run status
            fast_status = engine.workspace["fast_status"]
        except Exception:
            fast_status = "No"

        try:
            # Extract OutputAircraft
            fast_result_json = engine.workspace["fast_result_json"]
            output = build_json_data(normalize_json_data(json.loads(fast_result_json)))
        except Exception:
            try:
                fast_result = engine.workspace["fast_result"]
                # Convert MATLAB struct to Python dictionary
                output = matlab_to_python(fast_result)
            except Exception:
                output = {}

        # Keep default output as close to FAST as possible. Fixture generation
        # can opt into the comparison-friendly shape used by saved examples.
        if simplify_output and isinstance(output, dict):
            clean_output_fields(output)

        # FAST ran successfully and produced an output
        if str(fast_status) == "Yes":
            return {
                "status": "Yes",
                "log": log,
                "output": output,
            }
        else:
            return {
                "status": "No",
                "log": log,
                "output": output,
            }
    finally:
        # Quit MATLAB Engine
        engine.quit()
