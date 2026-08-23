"""Regression tests for headless plotting module imports."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module_name", ["src.gradcam", "src.evaluate"])
def test_plotting_module_overrides_unavailable_environment_backend(module_name: str) -> None:
    """Plotting modules must import even when a caller exports an unavailable backend."""
    env = os.environ.copy()
    env["MPLBACKEND"] = "module://matplotlib_inline.backend_inline"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                f"import {module_name}; import matplotlib; "
                "assert str(matplotlib.get_backend()).lower() == 'agg'"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("module_name", ["src.gradcam", "src.evaluate"])
def test_plotting_module_overrides_preselected_valid_backend(module_name: str) -> None:
    """Plotting modules must retain their unconditional headless-backend behavior."""
    env = os.environ.copy()
    env["MPLBACKEND"] = "svg"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import matplotlib; "
                "matplotlib.use('svg'); "
                "assert str(matplotlib.get_backend()).lower() == 'svg'; "
                f"import {module_name}; "
                "assert str(matplotlib.get_backend()).lower() == 'agg'"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
