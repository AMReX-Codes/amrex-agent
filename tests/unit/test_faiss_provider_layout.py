import json
from pathlib import Path

import pytest

from database.scripts import build_all_indices, build_index
import src.config as config_module
from src.config import AMReXAgentConfig


def test_config_uses_provider_scoped_faiss_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AMREX_DATABASE_PATH", str(tmp_path / "database"))

    config = AMReXAgentConfig(embedding_provider="amsc")

    assert config.faiss_db_path == tmp_path / "database" / "faiss" / "amsc"


def test_config_falls_back_to_flat_faiss_when_provider_dir_missing(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "database" / "faiss"
    (root / "level0").mkdir(parents=True)
    (root / "level0" / "physics_regimes.faiss").write_text("x", encoding="utf-8")
    monkeypatch.setenv("AMREX_DATABASE_PATH", str(tmp_path / "database"))

    config = AMReXAgentConfig(embedding_provider="amsc")

    assert config.faiss_db_path == root


def test_config_migrates_flat_layout_to_cborg(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "database" / "faiss"
    (root / "level0").mkdir(parents=True)
    (root / "level0" / "physics_regimes.faiss").write_text("x", encoding="utf-8")
    (root / "level1").mkdir(parents=True)
    (root / "level2").mkdir(parents=True)
    (root / "erf_case_structure").mkdir(parents=True)
    (root / "build_session_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AMREX_DATABASE_PATH", str(tmp_path / "database"))

    config = AMReXAgentConfig(embedding_provider="cborg")

    cborg_root = root / "cborg"
    assert config.faiss_db_path == cborg_root
    assert (cborg_root / "level0" / "physics_regimes.faiss").exists()
    assert (cborg_root / "level1").exists()
    assert (cborg_root / "level2").exists()
    assert (cborg_root / "erf_case_structure").exists()
    assert (cborg_root / "build_session_manifest.json").exists()
    assert not list(root.glob("*.faiss"))


def test_build_all_session_key_includes_provider_and_model() -> None:
    key_a = build_all_indices._session_key("2", "erf", "cborg", "text-embedding-3-small")
    key_b = build_all_indices._session_key("2", "erf", "cborg", "text-embedding-3-large")

    assert key_a != key_b


def test_build_all_manifest_merge_keeps_distinct_provider_model_entries(tmp_path: Path) -> None:
    root = tmp_path / "faiss" / "cborg"
    first = {
        "level": "2",
        "solver": "erf",
        "embedding_provider": "cborg",
        "embedding_model": "text-embedding-3-small",
        "manifest_path": "level2/erf_small.json",
    }
    second = {
        "level": "2",
        "solver": "erf",
        "embedding_provider": "cborg",
        "embedding_model": "text-embedding-3-large",
        "manifest_path": "level2/erf_large.json",
    }

    build_all_indices._write_build_session_manifest(root_output_dir=root, new_entries=[first])
    manifest_path = build_all_indices._write_build_session_manifest(
        root_output_dir=root,
        new_entries=[second],
    )

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 2


def test_build_all_resolve_effective_provider_prefers_cli() -> None:
    provider = build_all_indices._resolve_effective_provider("amsc", "cborg")
    assert provider == "amsc"


def test_build_index_resolve_effective_provider_prefers_provider_over_embedding() -> None:
    provider = build_index._resolve_effective_provider("amsc", "openai", "cborg")
    assert provider == "amsc"


def test_gitignore_has_provider_scoped_faiss_patterns() -> None:
    content = Path(".gitignore").read_text(encoding="utf-8")
    assert "!database/faiss/cborg/level0/" in content
    assert "!database/faiss/amsc/level0/" in content
    assert "!database/faiss/cborg/**/build_session_manifest.json" in content
    assert "!database/faiss/amsc/**/build_session_manifest.json" in content


def test_build_all_provider_resolution_hard_fails_when_unknown() -> None:
    with pytest.raises(ValueError):
        build_all_indices._resolve_effective_provider(None, None)


def test_build_all_provider_resolution_uses_config_fallback() -> None:
    assert build_all_indices._resolve_effective_provider(None, "cborg") == "cborg"


def test_provider_output_root_is_provider_scoped(tmp_path: Path) -> None:
    assert (
        build_all_indices._provider_output_root(tmp_path / "faiss", "amsc")
        == tmp_path / "faiss" / "amsc"
    )


def test_build_index_provider_resolution_fallback_order() -> None:
    assert build_index._resolve_effective_provider(None, "openai", "cborg") == "openai"
    assert build_index._resolve_effective_provider(None, None, "cborg") == "cborg"


def test_build_index_provider_resolution_fails_when_unknown() -> None:
    with pytest.raises(ValueError):
        build_index._resolve_effective_provider(None, None, None)


def test_build_index_resolve_output_dir_default_and_explicit(tmp_path: Path) -> None:
    explicit = build_index._resolve_output_dir(
        output_arg=tmp_path,
        effective_provider="cborg",
        code_name="erf",
        index_type="case_details",
    )
    assert explicit == tmp_path / "cborg" / "erf_case_details"

    default = build_index._resolve_output_dir(
        output_arg=None,
        effective_provider="cborg",
        code_name="erf",
        index_type="case_details",
    )
    assert default.name == "erf_case_details"
    assert default.parent.name == "cborg"


def test_has_flat_faiss_artifacts_ignores_known_provider_roots(tmp_path: Path) -> None:
    faiss_root = tmp_path / "faiss"
    (faiss_root / "cborg").mkdir(parents=True)
    (faiss_root / "amsc").mkdir(parents=True)
    assert config_module._has_flat_faiss_artifacts(faiss_root) is False

    (faiss_root / "level0").mkdir()
    assert config_module._has_flat_faiss_artifacts(faiss_root) is True


def test_migrate_flat_faiss_to_provider_noop_for_non_cborg(tmp_path: Path) -> None:
    faiss_root = tmp_path / "faiss"
    faiss_root.mkdir(parents=True)
    assert config_module.migrate_flat_faiss_to_provider(faiss_root, "amsc") is False


def test_resolve_faiss_db_path_for_provider_prefers_existing_provider_dir(tmp_path: Path) -> None:
    faiss_root = tmp_path / "faiss"
    provider_root = faiss_root / "amsc"
    provider_root.mkdir(parents=True)
    assert config_module.resolve_faiss_db_path_for_provider(faiss_root, "amsc") == provider_root


def test_resolve_faiss_db_path_for_provider_returns_provider_when_no_flat(tmp_path: Path) -> None:
    faiss_root = tmp_path / "faiss"
    faiss_root.mkdir(parents=True)
    assert (
        config_module.resolve_faiss_db_path_for_provider(faiss_root, "amsc")
        == faiss_root / "amsc"
    )


def test_resolve_faiss_db_path_for_provider_with_no_provider_returns_root(tmp_path: Path) -> None:
    faiss_root = tmp_path / "faiss"
    faiss_root.mkdir(parents=True)
    assert config_module.resolve_faiss_db_path_for_provider(faiss_root, None) == faiss_root
