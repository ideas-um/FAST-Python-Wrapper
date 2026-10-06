# tests/test_fast_nan_contract.py

"""Check merged input handling for FAST unspecified mission values."""

from math import isnan

import pytest

from core.aircraft_contract import clean_output_fields
from core.json_io import (
    JsonValidationError,
    load_json_data,
    read_raw_json_file,
)
from core.schema_validation import (
    validate_aircraft_json,
    validate_mission_json,
)
from tests.helpers import PROJECT_ROOT
import main as wrapper_module
from main import FAST_Python_Wrapper


DEFAULT_INPUT_PATH = PROJECT_ROOT / "examples" / "ATR42" / "InputAircraft.json"
DEFAULT_MISSION_PATH = PROJECT_ROOT / "examples" / "ATR42" / "Mission.json"


def fake_engine(evalc, workspace=None, quit=None):
    """Return the small MATLAB Engine surface the wrapper needs for unit tests."""

    def engine():
        pass

    engine.workspace = {} if workspace is None else workspace
    engine.evalc = evalc
    engine.quit = (lambda: None) if quit is None else quit
    return engine


def test_json_null_values_load_as_fast_nan():
    """Convert schema-level null placeholders into FAST NaN inputs."""

    data = {
        "Profile": {
            "ClbRate": [
                None,
            ],
        },
    }

    loaded = load_json_data(data)

    assert isnan(loaded["Profile"]["ClbRate"][0])


def test_schema_rejects_legacy_nan_string_in_mission_profile():
    """Keep mission profile NaN placeholders as JSON null, not strings."""

    data = read_raw_json_file(DEFAULT_MISSION_PATH)
    data["Profile"]["ClbRate"][0] = "NaN"

    with pytest.raises(JsonValidationError, match="ClbRate"):
        validate_mission_json(data)


def test_wrapper_requires_mission_profile(monkeypatch, tmp_path):
    """Require Mission.Profile before generating MATLAB FAST source."""

    def fail_evalc(script, nargout=1):
        raise AssertionError("FAST should not run without Mission.Profile")

    fast_path = tmp_path / "FAST"
    fast_path.mkdir()
    (fast_path / "Main.m").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper_module,
        "start_matlab",
        lambda path: fake_engine(fail_evalc),
    )

    result = FAST_Python_Wrapper({"Specs": {}}, {}, fast_path)

    assert result["status"] == "No"
    assert "Mission.Profile" in result["log"]
    assert result["output"] == {}


def test_wrapper_returns_status_log_output_dict(monkeypatch, tmp_path):
    """Keep FAST_Python_Wrapper() as a dict-in, dict-out API."""

    workspace = {}
    quit_calls = []

    def evalc(script, nargout=1):
        workspace["fast_status"] = "Yes"
        workspace["fast_result"] = {
            "Specs": {
                "Weight": {
                    "MTOW": 123.4567,
                },
            },
            "Mission": {
                "Profile": {},
            },
        }
        return "fake log"

    engine = fake_engine(evalc, workspace, lambda: quit_calls.append(True))
    fast_path = tmp_path / "FAST"
    fast_path.mkdir()
    (fast_path / "Main.m").write_text("", encoding="utf-8")
    monkeypatch.setattr(wrapper_module, "start_matlab", lambda path: engine)
    input_aircraft = {
        "Specs": {
            "Propulsion": {
                "PropArch": {
                    "Type": "C",
                },
            },
        },
    }
    mission = {
        "Profile": {},
    }

    result = FAST_Python_Wrapper(input_aircraft, mission, fast_path, simplify_output=True)

    assert result["status"] == "Yes"
    assert result["log"] == "fake log"
    assert result["output"]["Specs"]["Weight"]["MTOW"] == 123.4567
    assert quit_calls


def test_wrapper_reports_no_when_output_is_missing(monkeypatch, tmp_path):
    """Return a No status instead of assuming FAST produced OutputAircraft."""

    workspace = {}

    def evalc(script, nargout=1):
        workspace["fast_status"] = "No"
        workspace["fast_result"] = {}
        return "FAST did not converge"

    fast_path = tmp_path / "FAST"
    fast_path.mkdir()
    (fast_path / "Main.m").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper_module,
        "start_matlab",
        lambda path: fake_engine(evalc, workspace),
    )
    input_aircraft = {
        "Specs": {},
    }
    mission = {
        "Profile": {},
    }

    result = FAST_Python_Wrapper(input_aircraft, mission, fast_path, simplify_output=True)

    assert result == {
        "status": "No",
        "log": "FAST did not converge",
        "output": {},
    }


def test_wrapper_keeps_only_supported_prop_arch_output(monkeypatch, tmp_path):
    """Collapse FAST internal PropArch output back to a public Type object."""

    workspace = {}

    def evalc(script, nargout=1):
        workspace["fast_status"] = "Yes"
        workspace["fast_result"] = {
            "Geometry": {
                "Preset": "drop",
                "LengthSet": 1,
            },
            "Specs": {
                "Propulsion": {
                    "PropArch": {
                        "Type": "FAST internal",
                        "Unexpected": "drop",
                    },
                },
            },
            "Mission": {
                "Profile": {},
                "ProfileFxn": "drop",
            },
            "Settings": {
                "Dir": {
                    "Size": "drop",
                    "Oper": "keep",
                },
            },
        }
        return "fake log"

    fast_path = tmp_path / "FAST"
    fast_path.mkdir()
    (fast_path / "Main.m").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper_module,
        "start_matlab",
        lambda path: fake_engine(evalc, workspace),
    )
    input_aircraft = {
        "Specs": {
            "Propulsion": {
                "PropArch": {
                    "Type": "E",
                },
            },
        },
    }
    mission = {
        "Profile": {},
    }

    result = FAST_Python_Wrapper(input_aircraft, mission, fast_path, simplify_output=True)
    output = result["output"]

    assert "Preset" not in output["Geometry"]
    assert output["Geometry"]["LengthSet"] == 1
    assert output["Specs"]["Propulsion"]["PropArch"] == {}
    assert "ProfileFxn" not in output["Mission"]
    assert "Size" not in output["Settings"]["Dir"]
    assert output["Settings"]["Dir"]["Oper"] == "keep"


@pytest.mark.parametrize("arch_type", ["C", "E", "PHE", "SHE", "TE", "PE", "O"])
def test_output_keeps_fast_supported_prop_arch_labels(arch_type):
    """Collapse expanded FAST PropArch output for every supported label."""

    output = {
        "Specs": {
            "Propulsion": {
                "PropArch": {
                    "Type": arch_type,
                    "Arch": [
                        [1],
                    ],
                },
            },
        },
    }

    clean_output_fields(output)

    assert output["Specs"]["Propulsion"]["PropArch"] == {
        "Type": arch_type,
    }
