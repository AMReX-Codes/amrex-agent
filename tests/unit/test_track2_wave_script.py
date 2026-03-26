from pathlib import Path


def test_wave1_follow_up_command_uses_repo_relative_script_path() -> None:
    script_path = Path("scripts/paper/run_track2_waves.sh")
    text = script_path.read_text(encoding="utf-8")
    assert "When ready, run: ./scripts/paper/run_track2_waves.sh --wave2" in text
    assert "When ready, run: ./run_track2_waves.sh --wave2" not in text
