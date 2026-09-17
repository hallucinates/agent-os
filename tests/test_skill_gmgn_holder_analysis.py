"""Offline regression tests for the gmgn-holder-analysis script (issues #957, #2692).

``analyze.py`` indexed ``sys.argv[1]`` and ``sys.argv[2]`` at import time with
no length check, so running it with no arguments -- or with ``--help`` -- died
with an unhandled ``IndexError`` traceback instead of printing usage. Mirrors
the guard the sibling gmgn-wallet-score script already carries.

On non-UTF-8 console code pages, printing Unicode emoji and Chinese characters
raised ``UnicodeEncodeError``; ``analyze.py`` reconfigures stdio to UTF-8
with replacement at startup (#2692).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "src"
    / "agentos"
    / "skills"
    / "bundled"
    / "gmgn-holder-analysis"
    / "scripts"
    / "analyze.py"
)


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = {**os.environ, **env} if env is not None else None
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=run_env,
    )


@pytest.mark.parametrize(
    "args",
    [pytest.param((), id="no-args"), pytest.param(("0xabc",), id="one-arg")],
)
def test_missing_args_print_usage_and_exit_2(args: tuple[str, ...]) -> None:
    result = _run(*args)
    assert result.returncode == 2
    assert "Usage:" in result.stderr
    assert "<token_address>" in result.stderr
    assert "<chain>" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_flag_prints_usage_and_exits_0(flag: str) -> None:
    result = _run(flag)
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "<token_address>" in result.stdout
    assert "Traceback" not in result.stderr


def test_stdio_reconfigured_to_utf8_on_legacy_code_page() -> None:
    """Ensure analyze.py reconfigures stdio to UTF-8 so non-ASCII chars don't raise (#2692)."""
    script_str = str(SCRIPT).replace("\\", "/")
    probe_code = (
        "import sys\n"
        "code_text = open(r'" + script_str + "', encoding='utf-8').read()\n"
        "assert 'sys.stdout.reconfigure' in code_text, 'sys.stdout.reconfigure missing'\n"
        "assert 'sys.stderr.reconfigure' in code_text, 'sys.stderr.reconfigure missing'\n"
    )
    result = subprocess.run([sys.executable, "-c", probe_code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
