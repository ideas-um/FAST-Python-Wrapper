# test_json.py

import json
from pathlib import Path

from main import FAST_Python_Wrapper

project_dir = Path(__file__).resolve().parent
fast_dir = project_dir.parent / "FAST"
case_dir = project_dir / "examples" / "ATR42"

input_aircraft = json.loads(
    (case_dir / "InputAircraft.json").read_text(encoding="utf-8"),
)
mission = json.loads(
    (case_dir / "Mission.json").read_text(encoding="utf-8"),
)

result = FAST_Python_Wrapper(input_aircraft, mission, fast_dir)

print("Run success:", result["status"])
print(result["log"])

if result["status"] == "Yes":
    MTOW = result["output"]["Specs"]["Weight"]["MTOW"]
    print("MTOW:" + str(MTOW) + " kg")
