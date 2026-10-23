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

The `triet` integration stress tests additionally:

- Convert ATR42, B777-300ER, CeRAS, and ERJ175LR to PHE configurations.
- Use different nondefault takeoff, climb, cruise, and descent point counts.
- Size each aircraft, save native MATLAB state, recompute a fixed mission, and replay captured pointwise lambda histories through fresh MATLAB sessions.
- Require exact SI and EE physical histories while validating finite, mode-specific constraint residuals.
- Verify an infeasible supplied split worsens `PowerDeficit` relative to its recomputed baseline.
- Reject malformed segment counts, point counts, split widths, and power-management modes with useful diagnostics.
- Run custom `O` segment operational matrices through a full mission and require the same physics as the equivalent conventional architecture.

## How To Run Tests

From the repo root:
```
pytest
```
