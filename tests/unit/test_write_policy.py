from pathlib import Path

import pytest

from src.utils.write_policy import ensure_write_allowed, WritePolicyViolation


class DummyConfig:
    def __init__(self, output_dir, mode="deny"):
        self.output_dir = Path(output_dir)
        self.write_policy_mode = mode


def test_allows_write_under_output_dir(tmp_path):
    config = DummyConfig(output_dir=tmp_path, mode="deny")
    run_dir = tmp_path / "run_20250101_120000"

    ensure_write_allowed(run_dir, config, purpose="unit_test")


def test_denies_write_outside_output_dir(tmp_path):
    config = DummyConfig(output_dir=tmp_path, mode="deny")
    outside = tmp_path.parent / "other_dir"

    with pytest.raises(WritePolicyViolation):
        ensure_write_allowed(outside, config, purpose="unit_test")
