from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agentos"
    / "skills"
    / "bundled"
    / "http-fetch"
    / "scripts"
    / "http_fetch.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("http_fetch", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_truncate_bytes_respects_max_bytes_limit() -> None:
    module = _load_module()
    raw = b"Hello, World! This is a long test payload."
    max_bytes = 15

    truncated = module._truncate_bytes(raw, max_bytes)

    assert len(truncated) <= max_bytes
    assert truncated.endswith(b"\xe2\x80\xa6")
    assert truncated == b"Hello, World\xe2\x80\xa6"


def test_truncate_bytes_preserves_utf8_char_boundaries() -> None:
    module = _load_module()
    # '€' is 3 bytes: \xe2\x82\xac
    raw = b"Hello, \xe2\x82\xac world!"

    # Slicing raw at 11 bytes normally cuts right inside '€' (\xe2)
    truncated = module._truncate_bytes(raw, 11)

    assert len(truncated) <= 11
    # Must not contain replacement character '\ufffd'
    decoded = truncated.decode("utf-8")
    assert "\ufffd" not in decoded
    assert decoded.endswith("…")


def test_http_fetch_main_truncation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_module()

    def fake_fetch(_url: str, _method: str, _body: bytes, _timeout: float):
        return 200, b"abcdefghijklmnopqrstuvwxyz", "OK"

    monkeypatch.setattr(module, "_fetch", fake_fetch)
    monkeypatch.setattr(module.sys.stdin, "isatty", lambda: True)

    status = module.main(["--url", "https://example.com", "--max-bytes", "10"])

    assert status == 0
    out = capsys.readouterr().out
    assert len(out.encode("utf-8")) <= 10
    assert out.endswith("…")
