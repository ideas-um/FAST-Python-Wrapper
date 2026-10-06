# test_json.py

from pathlib import Path

from core.json_io import load_json_data, read_raw_json_file
from main import FAST_Python_Wrapper

project_dir = Path(__file__).resolve().parent
fast_dir = project_dir.parent / "FAST"
case_dir = project_dir / "examples" / "ATR42"

input_aircraft = load_json_data(read_raw_json_file(case_dir / "InputAircraft.json"))
mission = load_json_data(read_raw_json_file(case_dir / "Mission.json"))

result = FAST_Python_Wrapper(input_aircraft, mission, fast_dir)

print("Run success:", result["status"])
print(result["log"])

if result["status"] == "Yes":
    MTOW = result["output"]["Specs"]["Weight"]["MTOW"]
    print("MTOW:" + str(MTOW) + " kg")
