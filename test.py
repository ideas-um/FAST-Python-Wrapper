# test.py

from pathlib import Path

from numpy import nan

from main import FAST_Python_Wrapper

project_dir = Path(__file__).resolve().parent
fast_dir = project_dir.parent / "FAST"

input_aircraft = {
    "Specs": {
        "TLAR": {
            "Class": "Turbofan", # Turbofan, Turboprop
            "MaxPax": 180,
        },
        "Performance": {
            "Range": 4630000,
        },
        "Aero": {
            "L_D": {
                "Method": "ConstantLD",
                "ClbCF": 1,
                "CrsCF": 1,
                "Clb": 13,
                "Crs": 17,
                "Des": 13,
            },
            "W_S": {
                "SLS": 739.8499,
            },
        },
        "Propulsion": {
            "PropArch": {
                "Type": "C", # C, E, PHE, SHE, TE, PE, or O
            },
            # Turboprop: AE2100_D3, AE501D_22G, Allison_250_C30G, PT6A_114A, PW_123, PW_127M, TPE331_14GR_805H
            # Turbofan: AE3007A, CeRAS, CF34_8E5, CF6_80C2_B7F, LEAP_1A26, PW_1919G, PW_2037, RB211_22B_02, Trent_970B_84
            "Engine": "CF34_8E5"
        },
        "Power": {
            "P_W": {},
        },
    },
}

mission = {
    "Profile": {
        "Target": {
            "Valu": [4630000],
            "Type": ["Dist"],
        },
        "Segs": ["Climb", "Cruise", "Descent"],
        "ID": [1, 1, 1],
        "AltBeg": [0, 10668, 10668],
        "AltEnd": [10668, 10668, 0],
        "ClbRate": [nan, nan, nan],
        "VelBeg": [0.2, 0.78, 0.78],
        "VelEnd": [0.78, 0.78, 0.2],
        "TypeBeg": ["Mach", "Mach", "Mach"],
        "TypeEnd": ["Mach", "Mach", "Mach"],
    },
}

result = FAST_Python_Wrapper(input_aircraft, mission, fast_dir)

print("Run success:", result["status"])
print(result["log"])

if result["status"] == "Yes":
    MTOW = result["output"]["Specs"]["Weight"]["MTOW"]
    print("MTOW:" + str(MTOW) + " kg")
