# FAST Python Wrapper

Python wrapper for running [Future Aircraft Sizing Tool (FAST)](https://github.com/ideas-um/FAST) through MATLAB Engine.


## Running FAST-Python-Wrapper

The core wrapper accepts an `input_aircraft` dictionary, a separate `mission` dictionary, and the local path to FAST. JSON files in `examples/` are just an interface pattern for loading those dictionaries.

```python


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
# print(result["log"])

if result["status"] == "Yes":
    MTOW = result["output"]["Specs"]["Weight"]["MTOW"]
    print("MTOW:" + str(MTOW) + " kg")


```


## FAST Coverage

The wrapper passes aircraft data through to FAST and keeps wrapper-side rules limited to the MATLAB bridge. Known FAST package functions can be written as short names, such as engine specs, aero methods, and geometry presets. New FAST package functions also work when their function name is a valid MATLAB identifier.

Custom `O` propulsion architectures support fixed numeric vectors or matrices, and JSON inputs can use explicit `_matlab_expression` marker objects when FAST needs a function handle. To vary a fixed topology by mission segment, provide paired `OperUpsBySegment` and `OperDwnBySegment` lists; each list contains one numeric matrix per `Mission.Profile.Segs` row.

Segment-specific `OperUpsBySegment` and `OperDwnBySegment` support requires FAST branch `gengnns4gpsa`. The compatible FAST revision pinned by ASTRA is `adeff17cd7734cbd669cb59499556caf6ff248af`; FAST `main` at `482e77b921d616d00d9cdb5c0c673d55f511c52b` does not consume these fields.

By default, `FAST_Python_Wrapper()` returns the full FAST output after converting MATLAB values into Python data. Use `simplify_output=True` only when regenerating or comparing the repository's simplified JSON fixtures.

Core API shape:

```python
result = FAST_Python_Wrapper(input_aircraft, mission, fast_dir)
```

`input_aircraft`, `mission`, and `result["output"]` are normal Python dictionaries. File loading is optional and belongs at the application/example boundary.


## Requirements

- A local FAST directory
- Use a virtual environment with a Python version that is compatible with MATLAB Engine on [MATLAB Official Website](https://www.mathworks.com/support/requirements/python-compatibility.html). Edit [`pyproject.toml`](https://github.com/triet228/FAST-Python-Wrapper/blob/main/pyproject.toml) to match the correct python and matlabengine version.

> [!WARNING]
> Please make sure your Python version is compatible with MATLAB Engine and it's reflected in both your virtual environment and [`pyproject.toml`](https://github.com/triet228/FAST-Python-Wrapper/blob/main/pyproject.toml).


## Installations

1. Clone this [GitHub repository](https://github.com/triet228/FAST-Python-Wrapper) to your machine.

2. Confirm Python version is compatible with MATLAB Engine. Edit [`pyproject.toml`](https://github.com/triet228/FAST-Python-Wrapper/blob/main/pyproject.toml) to match the correct python and matlabengine version.
> [!WARNING]
> Please confirm your Python version is compatible with MATLAB Engine on [MATLAB Official Website](https://www.mathworks.com/support/requirements/python-compatibility.html)

3. Install dependencies:
> [!TIP]
> Command line can be run in VS Code Terminal
```
pip install -e .
```

4. Check that Python can import MATLAB Engine:
```powershell
python -c "import matlab.engine; print('MATLAB Engine OK')"
```
If this gives error, you will need to debug this before continue. If this prints `MATLAB Engine OK`, the environment is ready.
> [!WARNING]
> One bug might be that your Python version is not compatible with MATLAB Engine. Please check on [MATLAB Official Website](https://www.mathworks.com/support/requirements/python-compatibility.html). Edit [`pyproject.toml`](https://github.com/triet228/FAST-Python-Wrapper/blob/main/pyproject.toml) to match the correct python and matlabengine version. Then redo step 4 `pip install -e .` to install dependencies.

> [!TIP]
> Inside MATLAB, you can run `which matlab` to know where MATLAB is installed.
