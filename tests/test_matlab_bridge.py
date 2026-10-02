# tests/test_matlab_bridge.py

"""Verify MATLAB session setup required by FAST's relative native assets."""

import sys
from types import ModuleType

from core.matlab_bridge import start_matlab


def test_start_matlab_uses_fast_as_working_directory(tmp_path, monkeypatch):
    """Run from FAST's root because geometry packages open relative asset paths."""
    calls = []

    class FakeEngine:
        def genpath(self, path):
            calls.append(("genpath", path))
            return path

        def addpath(self, path, nargout=0):
            calls.append(("addpath", path, nargout))

        def cd(self, path, nargout=0):
            calls.append(("cd", path, nargout))

    engine_module = ModuleType("matlab.engine")
    engine_module.start_matlab = FakeEngine
    matlab_module = ModuleType("matlab")
    matlab_module.engine = engine_module
    monkeypatch.setitem(sys.modules, "matlab", matlab_module)
    monkeypatch.setitem(sys.modules, "matlab.engine", engine_module)

    engine = start_matlab(tmp_path)

    assert isinstance(engine, FakeEngine)
    assert calls[-1] == ("cd", str(tmp_path), 0)
