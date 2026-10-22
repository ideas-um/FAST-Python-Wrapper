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


def FAST_Python_Wrapper(
    input_aircraft,
    mission,
    fast_path,
    simplify_output=False,
    state_input_path=None,
    state_output_path=None,
):
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
        Pass state_output_path to preserve the native MATLAB aircraft needed
            for a later fixed-aircraft run. Pass that artifact back through
            state_input_path to retain function handles and derived graph data
            that cannot be represented in JSON.

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
            aircraft_setup = _aircraft_setup(aircraft_matlab, state_input_path)
            state_save = _state_save(state_output_path)
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
                requested_aircraft = {aircraft_matlab};
                {aircraft_setup}
                mission_profile = @(Aircraft) setfield(Aircraft, "Mission", "Profile", {mission_matlab});
                fast_result = struct();
                fast_result_json = '';
                fast_status = 'No';
                try
                    fast_result = Main(aircraft_spec, mission_profile);
                    {state_save}
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


def _aircraft_setup(aircraft_matlab, state_input_path):
    """Build MATLAB statements for a fresh or native-state FAST run."""
    if state_input_path is None:
        return "aircraft_spec = requested_aircraft;"
    state_path = _matlab_string(state_input_path)
    return f"""
                saved_state = load('{state_path}', 'fast_result');
                aircraft_spec = saved_state.fast_result;
                aircraft_spec.Settings.Analysis = requested_aircraft.Settings.Analysis;
                aircraft_spec.Specs.Power.LamUps = requested_aircraft.Specs.Power.LamUps;
                aircraft_spec.Specs.Power.LamDwn = requested_aircraft.Specs.Power.LamDwn;
    """.strip()


def _state_save(state_output_path):
    """Build the optional MATLAB statement that preserves native FAST state."""
    if state_output_path is None:
        return ""
    state_path = Path(state_output_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    return f"save('{_matlab_string(state_path)}', 'fast_result', '-v7.3');"


def _matlab_string(value):
    """Escape one filesystem path for a single-quoted MATLAB string."""
    return str(Path(value).resolve()).replace("'", "''")
