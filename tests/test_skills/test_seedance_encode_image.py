"""Tests for seedance generate_video.py image path encoding and error handling."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agentos"
    / "skills"
    / "bundled"
    / "seedance-2-prompt"
    / "scripts"
    / "generate_video.py"
)


def _load_script() -> object:
    spec = importlib.util.spec_from_file_location("generate_video", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_video"] = module
    spec.loader.exec_module(module)
    return module


def test_encode_input_image_valid_file(tmp_path: Path) -> None:
    module = _load_script()
    image_file = tmp_path / "test.png"
    image_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01")

    url = module._encode_input_image(str(image_file))  # type: ignore[attr-defined]
    assert url.startswith("data:image/png;base64,")


def test_encode_input_image_directory_raises_runtime_error(tmp_path: Path) -> None:
    module = _load_script()
    img_dir = tmp_path / "fake_dir.png"
    img_dir.mkdir()

    with pytest.raises(RuntimeError, match="Image not found or is a directory"):
        module._encode_input_image(str(img_dir))  # type: ignore[attr-defined]


def test_encode_input_image_nonexistent_file_raises_runtime_error(tmp_path: Path) -> None:
    module = _load_script()
    missing_file = tmp_path / "nonexistent.png"

    with pytest.raises(RuntimeError, match="Image not found or is a directory"):
        module._encode_input_image(str(missing_file))  # type: ignore[attr-defined]
