from pathlib import Path


def test_llm_calls_go_through_helper():
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    offenders = []
    for path in src_root.rglob("*.py"):
        if path.name == "llm_calls.py":
            continue
        text = path.read_text()
        if "chat.completions.create" in text:
            offenders.append(path.relative_to(repo_root))

    assert offenders == [], f"Direct chat.completions.create usage found: {offenders}"
