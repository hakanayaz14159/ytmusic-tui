"""Packaging contract: installed name, stylesheet, and python -m entry."""

import subprocess
import sys
from importlib.resources import files

from ytmusic_tui import __version__


def test_package_includes_stylesheet() -> None:
    stylesheet = files("ytmusic_tui").joinpath("app.tcss")
    assert stylesheet.is_file()


def test_python_module_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ytmusic_tui", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout
