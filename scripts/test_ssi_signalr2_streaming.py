#!/usr/bin/env python
"""Compatibility entrypoint for SSI ASP.NET SignalR classic streaming tests."""
from __future__ import annotations

from pathlib import Path
import runpy

SCRIPT = Path(__file__).with_name("test_ssi_streaming.py")
runpy.run_path(str(SCRIPT), run_name="__main__")
