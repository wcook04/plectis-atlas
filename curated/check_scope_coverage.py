#!/usr/bin/env python3
"""Compatibility command; the maintained validator is in scripts/check_scope_coverage.py."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/check_scope_coverage.py"),
                   run_name="__main__")
