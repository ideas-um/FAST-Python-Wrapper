# FAST Python Wrapper Tests

These tests verify that the FAST Python Wrapper stays aligned with MATLAB FAST. They compare results from wrapper runs against MATLAB FAST outputs.

## Test Algorithms

1. Load aircraft dictionaries from `examples/*/InputAircraft.json` and mission dictionaries from `examples/*/Mission.json`.
2. Run FAST Python Wrapper with those in-memory dictionaries.
3. Require `status` to be `Yes`, then recursively compare the returned `output` dictionary against the saved `OutputAircraft.json`.

These tests compare all comparable fields in `OutputAircraft.json`, including
nested structs, numeric arrays, logical values, strings, cells, and function
handle text. A few machine-local runtime fields are intentionally excluded:

- `Aircraft.Settings.Plotting`: FAST can mutate plotting state independently of the aircraft and mission result.
- `Aircraft.Settings.Dir.*`: FAST records the local checkout/runtime paths.

## How To Run Tests

From the repo root:
```
pytest
```
