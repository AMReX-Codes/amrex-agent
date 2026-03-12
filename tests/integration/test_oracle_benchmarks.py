import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from database.configs import discover_code_configs
from database.indexing.level0_builder import Level0Builder
from database.indexing.level0_searcher import Level0Searcher
from src.benchmark_runner import run_model_benchmark, validate_case_files


class DeterministicEmbedder:
    """Deterministic hash-based embedder for offline Level-0 routing tests."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def expand_documents(self, documents, metadata):
        return documents, metadata

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % self.dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    def embed_texts(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str):
        return self._embed(text)


@dataclass(frozen=True)
class OracleRouteCase:
    id: str
    difficulty: str
    prompt: str
    expected_solver: str
    expected_case: str
    status: str = "pass"
    xfail_reason: str = ""


def _load_level0_oracle_cases() -> list[dict]:
    data_file = Path(__file__).resolve().parents[1] / "data" / "level0_ab_prompts.json"
    return json.loads(data_file.read_text(encoding="utf-8"))


def _build_level0_searcher(tmp_path: Path) -> Level0Searcher:
    embedder = DeterministicEmbedder()
    index_dir = tmp_path / "level0"
    Level0Builder(embedder=embedder).build(output_dir=index_dir)
    return Level0Searcher(index_dir=index_dir, embedder=embedder)


def _oracle_solver_accuracy(searcher: Level0Searcher, prompts: list[dict]) -> float:
    if not prompts:
        return 0.0

    hits = 0
    for item in prompts:
        result = searcher.search(item["prompt"], top_k=1)
        if result and result[0]["code"] == item["expected_solver"]:
            hits += 1
    return hits / len(prompts)


def _load_benchmark_case_catalog() -> dict[str, list[dict[str, object]]]:
    """
    Load canonical benchmark case metadata from benchmark/cases/*.yaml.

    This is the single source of truth for in-scope solver case paths and
    difficulty tiers used by oracle routing tests.
    """
    cases_dir = Path("benchmark/cases")
    catalog: dict[str, list[dict[str, object]]] = {}
    if not cases_dir.exists():
        return catalog

    for yaml_path in sorted(cases_dir.glob("*.yaml")):
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        solver = str(data.get("solver", "")).strip()
        if not solver:
            continue
        case_entries = []
        for case in data.get("cases", []):
            case_path = str(case.get("case_dir", "")).strip()
            if not case_path:
                continue
            tags: list[str] = [str(case.get("case_name", ""))]
            tags.extend(str(p) for p in case.get("physics", []) if p)
            tags.extend(str(t) for t in case.get("tags", []) if t)
            description = str(case.get("description", "")).strip()
            if description:
                tags.append(description)
            case_entries.append(
                {
                    "id": str(case.get("id", "")).strip(),
                    "path": case_path,
                    "case_name": str(case.get("case_name", "")).strip(),
                    "difficulty_tier": str(case.get("difficulty_tier", "medium")).strip().lower() or "medium",
                    "tags": tags,
                }
            )
        if case_entries:
            catalog[solver] = case_entries

    return catalog


BENCHMARK_CASE_CATALOG = _load_benchmark_case_catalog()


def _config_for_solver(code_name: str):
    for config in discover_code_configs():
        if getattr(config, "code_name", None) == code_name:
            return config
    raise AssertionError(f"No config class found for solver code '{code_name}'")


def _tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in re.findall(r"[A-Za-z0-9_]+", text):
        lower = raw.lower()
        if lower:
            tokens.add(lower)
        # Split camel case so `DoubleGyre` can match `double gyre`.
        expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
        for part in re.findall(r"[A-Za-z0-9_]+", expanded.lower()):
            if part:
                tokens.add(part)
    return tokens


def _candidate_similarity(prompt: str, case_path: str, tags: list[str]) -> float:
    prompt_tokens = _tokenize(prompt)
    case_tokens = _tokenize(case_path)
    for tag in tags:
        case_tokens.update(_tokenize(tag))
    if not case_tokens:
        return 0.0
    return len(prompt_tokens.intersection(case_tokens)) / len(case_tokens)


def _oracle_catalog() -> dict[str, list[dict[str, object]]]:
    # Single source of truth: start from benchmark/cases YAML metadata.
    catalog: dict[str, list[dict[str, object]]] = {
        solver: [{"path": entry["path"], "tags": list(entry.get("tags", []))} for entry in entries]
        for solver, entries in BENCHMARK_CASE_CATALOG.items()
    }

    # Explicit, auditable overrides for known benchmark-catalog gaps.
    overrides: dict[str, list[dict[str, object]]] = {
        "AMReX": [
            {"path": "Tests/Amr/Advection_AmrCore", "tags": ["advection", "tutorial", "passive scalar", "amr"]},
        ],
        "ERF": [
            {"path": "Exec/RegTests/Bubble", "tags": ["thermal bubble", "dry convection", "stratified atmosphere"]},
            {"path": "Exec/CanonicalFlows/SquallLine_2D", "tags": ["squall line", "moist convection", "cold air outflow"]},
        ],
        "incflo": [
            {"path": "benchmark_Godunov", "tags": ["godunov", "incompressible benchmark"]},
            {"path": "double_shear_layer", "tags": ["shear layer"]},
            {"path": "lid_driven_cavity", "tags": ["lid driven cavity"]},
            {"path": "taylor_green_vortex", "tags": ["taylor green", "vortex"]},
            {"path": "channel_flow", "tags": ["channel flow"]},
            {"path": "vortex_patch", "tags": ["vortex patch"]},
        ],
        "WarpX": [
            {"path": "Examples/Physics_applications/laser_acceleration", "tags": ["laser acceleration", "plasma acceleration"]},
            {"path": "Examples/Physics_applications/plasma_acceleration", "tags": ["plasma acceleration", "beam"]},
            {"path": "Examples/Tests/gaussian_beam", "tags": ["gaussian beam", "electromagnetic beam"]},
        ],
    }

    for solver, entries in overrides.items():
        existing = {str(item["path"]).strip().lower() for item in catalog.get(solver, [])}
        merged = list(catalog.get(solver, []))
        for entry in entries:
            normalized = str(entry["path"]).strip().lower()
            if normalized in existing:
                continue
            merged.append(entry)
        if merged:
            catalog[solver] = merged

    return catalog


def _synchronize_oracle_cases_with_benchmark(cases: list[OracleRouteCase]) -> list[OracleRouteCase]:
    """
    Synchronize oracle case path + difficulty from benchmark catalog when available.
    """
    lookup: dict[tuple[str, str], dict[str, object]] = {}
    for solver, entries in BENCHMARK_CASE_CATALOG.items():
        for entry in entries:
            lookup[(solver, str(entry["path"]).strip().lower())] = entry

    synced: list[OracleRouteCase] = []
    for case in cases:
        key = (case.expected_solver, case.expected_case.strip().lower())
        benchmark_entry = lookup.get(key)
        if benchmark_entry:
            synced.append(
                OracleRouteCase(
                    id=case.id,
                    difficulty=case.difficulty,
                    prompt=case.prompt,
                    expected_solver=case.expected_solver,
                    expected_case=str(benchmark_entry.get("path", case.expected_case)),
                    status=case.status,
                    xfail_reason=case.xfail_reason,
                )
            )
        else:
            synced.append(case)
    return synced


def _is_benchmark_backed(case: OracleRouteCase) -> bool:
    entries = BENCHMARK_CASE_CATALOG.get(case.expected_solver, [])
    paths = {str(entry["path"]).strip().lower() for entry in entries}
    return case.expected_case.strip().lower() in paths


def _benchmark_backed_gate_cases(cases: list[OracleRouteCase]) -> list[OracleRouteCase]:
    return [case for case in cases if _is_benchmark_backed(case)]


def _nonbenchmark_gate_cases(cases: list[OracleRouteCase]) -> list[OracleRouteCase]:
    return [case for case in cases if not _is_benchmark_backed(case)]


def _select_case_for_solver(prompt: str, solver: str) -> str:
    catalog = _oracle_catalog().get(solver, [])
    solver_config = _config_for_solver(solver)

    if not catalog:
        return getattr(solver_config, "default_exec_repo_path", "")

    candidates: list[dict] = []
    for entry in catalog:
        case_path = str(entry["path"])
        tags = list(entry["tags"])
        semantic_score = _candidate_similarity(prompt, case_path, tags)
        combined = semantic_score
        if "devtest" in case_path.lower() and str(solver).lower() == "erf":
            # Keep ERF DevTests below RegTests for routing stability.
            combined *= 0.5
        candidates.append(
            {
                "case": case_path,
                "score": combined,
                "metadata": {"repo_path": case_path},
            }
        )

    priority_cases = list(getattr(solver_config, "priority_cases", []) or [])
    priority_set = {p.strip("/").lower() for p in priority_cases}

    def _priority_bonus(case_path: str) -> float:
        norm = case_path.strip("/").lower()
        if norm in priority_set:
            return 0.08
        for priority in priority_set:
            if norm.startswith(f"{priority}/") or priority.startswith(f"{norm}/"):
                return 0.08
        return 0.0

    ranked = sorted(
        candidates,
        key=lambda c: float(c["score"]) + _priority_bonus(str(c["case"])),
        reverse=True,
    )
    return str(ranked[0]["case"])


def run_selection_pipeline(prompt: str, searcher: Level0Searcher) -> SimpleNamespace:
    result = searcher.search(prompt, top_k=1)
    assert result, f"No Level-0 selection result returned for prompt: {prompt!r}"
    solver = result[0]["code"]
    selected_case = _select_case_for_solver(prompt, solver)
    return SimpleNamespace(solver=solver, selected_case=selected_case)


_ORACLE_GATE_CASES_RAW: list[OracleRouteCase] = [
    # Easy (8)
    OracleRouteCase(
        id="oracle_easy_amrex_advection_amrcore",
        difficulty="easy",
        prompt="Run the AMReX advection tutorial with passive scalar transport on nested AMR grids.",
        expected_solver="AMReX",
        expected_case="Tests/Amr/Advection_AmrCore",
    ),
    OracleRouteCase(
        id="oracle_easy_pelec_pmf",
        difficulty="easy",
        prompt="Use compressible premixed methane PMF setup for a reacting flame benchmark.",
        expected_solver="PeleC",
        expected_case="Exec/RegTests/PMF",
    ),
    OracleRouteCase(
        id="oracle_easy_pelelmex_flamesheet",
        difficulty="easy",
        prompt="Use a low-Mach FlameSheet diffusion-flame-sheet configuration with detailed transport.",
        expected_solver="PeleLMeX",
        expected_case="Exec/RegTests/FlameSheet",
    ),
    OracleRouteCase(
        id="oracle_easy_erf_bubble",
        difficulty="easy",
        prompt="Run an atmospheric thermal bubble dry convection benchmark in a stratified atmosphere.",
        expected_solver="ERF",
        expected_case="Exec/RegTests/Bubble",
    ),
    OracleRouteCase(
        id="oracle_easy_remora_seamount",
        difficulty="easy",
        prompt="Model baroclinic coastal-ocean circulation over seamount topography.",
        expected_solver="REMORA",
        expected_case="Exec/Seamount",
    ),
    OracleRouteCase(
        id="oracle_easy_remora_upwelling",
        difficulty="easy",
        prompt="Simulate wind-driven upwelling in a coastal ocean channel.",
        expected_solver="REMORA",
        expected_case="Exec/Upwelling",
    ),
    OracleRouteCase(
        id="oracle_easy_pelec_sedov",
        difficulty="easy",
        prompt="Use a Sedov blast wave hydro regression case for compressible flow verification.",
        expected_solver="PeleC",
        expected_case="Exec/RegTests/Sedov",
    ),
    OracleRouteCase(
        id="oracle_easy_erf_squallline_2d",
        difficulty="easy",
        prompt="Run a moist squall-line convection scenario with cold-air outflow dynamics.",
        expected_solver="ERF",
        expected_case="Exec/CanonicalFlows/SquallLine_2D",
    ),
    # Medium (8)
    OracleRouteCase(
        id="oracle_medium_erf_densitycurrent",
        difficulty="medium",
        prompt="ERF DryRegTests DensityCurrent atmospheric stratification nonreacting flow.",
        expected_solver="ERF",
        expected_case="Exec/DryRegTests/DensityCurrent",
    ),
    OracleRouteCase(
        id="oracle_medium_erf_abl",
        difficulty="medium",
        prompt="Atmospheric boundary-layer neutral scaling study with terrain-influenced wind profile.",
        expected_solver="ERF",
        expected_case="Exec/ABL",
    ),
    OracleRouteCase(
        id="oracle_medium_pelec_tg",
        difficulty="medium",
        prompt="Run a compressible Taylor-Green vortex (TG) turbulence benchmark in the PeleC/CNS family.",
        expected_solver="PeleC",
        expected_case="Exec/RegTests/TG",
    ),
    OracleRouteCase(
        id="oracle_medium_pelelmex_taylorgreen",
        difficulty="medium",
        prompt="Low-Mach Taylor-Green vortex setup with variable-density effects.",
        expected_solver="PeleLMeX",
        expected_case="Exec/RegTests/TaylorGreen",
    ),
    OracleRouteCase(
        id="oracle_medium_pelelmex_counterflow",
        difficulty="medium",
        prompt="Create an opposed-flow counterflow diffusion flame case with detailed chemistry.",
        expected_solver="PeleLMeX",
        expected_case="Exec/Production/CounterFlow",
    ),
    OracleRouteCase(
        id="oracle_medium_remora_doublegyre",
        difficulty="medium",
        prompt="Run the REMORA DoubleGyre ocean circulation benchmark with two recirculating gyres in a periodic basin under wind forcing.",
        expected_solver="REMORA",
        expected_case="Exec/DoubleGyre",
    ),
    OracleRouteCase(
        id="oracle_medium_remora_channel_test",
        difficulty="medium",
        prompt="Coastal channel turbulence experiment for ocean circulation diagnostics.",
        expected_solver="REMORA",
        expected_case="Exec/Channel_Test",
    ),
    OracleRouteCase(
        id="oracle_medium_remora_doublyperiodic",
        difficulty="medium",
        prompt="Doubly periodic stratified ocean test with idealized circulation forcing.",
        expected_solver="REMORA",
        expected_case="Exec/DoublyPeriodic",
    ),
    # Hard (4)
    OracleRouteCase(
        id="oracle_hard_pelec_jetflame_conflict",
        difficulty="hard",
        prompt="Low-speed sounding description but the core objective is a compressible reacting jet flame with fuel injection and shocks.",
        expected_solver="PeleC",
        expected_case="Exec/Production/JetFlame",
    ),
    OracleRouteCase(
        id="oracle_hard_pelelmex_jetincrossflow",
        difficulty="hard",
        prompt="Design a low-Mach reacting jet in crossflow where diffusion and transport dominate over shock dynamics.",
        expected_solver="PeleLMeX",
        expected_case="Exec/Production/JetInCrossflow",
    ),
    OracleRouteCase(
        id="oracle_hard_incflo_benchmark_godunov",
        difficulty="hard",
        prompt="Run incompressible benchmark Godunov flow with channel-like vortical structures.",
        expected_solver="incflo",
        expected_case="benchmark_Godunov",
        status="xfail",
        xfail_reason="incflo L2 catalog not present — requires local repo and index build",
    ),
    OracleRouteCase(
        id="oracle_hard_warpx_laser_acceleration",
        difficulty="hard",
        prompt="Model laser-plasma particle acceleration with electromagnetic PIC dynamics.",
        expected_solver="WarpX",
        expected_case="Examples/Physics_applications/laser_acceleration",
        status="xfail",
        xfail_reason="WarpX L2 catalog not present — requires local repo and index build",
    ),
]

ORACLE_GATE_CASES: list[OracleRouteCase] = _synchronize_oracle_cases_with_benchmark(_ORACLE_GATE_CASES_RAW)


ORACLE_EXTENDED_XFAIL_CASES: list[OracleRouteCase] = [
    OracleRouteCase(
        id="oracle_xfail_incflo_double_shear_layer",
        difficulty="medium",
        prompt="Incompressible double shear layer benchmark with non-reacting vortical roll-up.",
        expected_solver="incflo",
        expected_case="double_shear_layer",
        status="xfail",
        xfail_reason="incflo L2 catalog not present — requires local repo and index build",
    ),
    OracleRouteCase(
        id="oracle_xfail_incflo_lid_driven_cavity",
        difficulty="easy",
        prompt="Classical incompressible lid-driven cavity flow test at moderate Reynolds number.",
        expected_solver="incflo",
        expected_case="lid_driven_cavity",
        status="xfail",
        xfail_reason="incflo L2 catalog not present — requires local repo and index build",
    ),
    OracleRouteCase(
        id="oracle_xfail_incflo_taylor_green_vortex",
        difficulty="easy",
        prompt="Incompressible Taylor-Green vortex decay benchmark.",
        expected_solver="incflo",
        expected_case="taylor_green_vortex",
        status="xfail",
        xfail_reason="incflo L2 catalog not present — requires local repo and index build",
    ),
    OracleRouteCase(
        id="oracle_xfail_incflo_channel_flow",
        difficulty="easy",
        prompt="Non-reacting channel flow benchmark for incompressible solver verification.",
        expected_solver="incflo",
        expected_case="channel_flow",
        status="xfail",
        xfail_reason="incflo L2 catalog not present — requires local repo and index build",
    ),
    OracleRouteCase(
        id="oracle_xfail_incflo_vortex_patch",
        difficulty="medium",
        prompt="Incompressible vortex patch advection benchmark with Godunov update.",
        expected_solver="incflo",
        expected_case="vortex_patch",
        status="xfail",
        xfail_reason="incflo L2 catalog not present — requires local repo and index build",
    ),
    OracleRouteCase(
        id="oracle_xfail_warpx_plasma_acceleration",
        difficulty="medium",
        prompt="Plasma acceleration scenario using electromagnetic particle-in-cell evolution.",
        expected_solver="WarpX",
        expected_case="Examples/Physics_applications/plasma_acceleration",
        status="xfail",
        xfail_reason="WarpX L2 catalog not present — requires local repo and index build",
    ),
    OracleRouteCase(
        id="oracle_xfail_warpx_gaussian_beam",
        difficulty="medium",
        prompt="Propagate a Gaussian beam in a WarpX electromagnetic test setup.",
        expected_solver="WarpX",
        expected_case="Examples/Tests/gaussian_beam",
        status="xfail",
        xfail_reason="WarpX L2 catalog not present — requires local repo and index build",
    ),
]


@pytest.fixture(scope="module")
def level0_searcher(tmp_path_factory: pytest.TempPathFactory) -> Level0Searcher:
    return _build_level0_searcher(tmp_path_factory.mktemp("level0_oracle"))


@pytest.mark.integration
@pytest.mark.parametrize("case", ORACLE_GATE_CASES, ids=lambda c: c.id)
def test_oracle_gate_routing(case: OracleRouteCase, level0_searcher: Level0Searcher) -> None:
    """
    Difficulty-tiered oracle routing gate (v2605-aligned).

    Uses natural-language prompts with subtle and conflicting cues to reduce
    keyword-overfit risk while locking expected solver/case routing behavior.
    """
    if case.status == "xfail":
        pytest.xfail(case.xfail_reason)

    result = run_selection_pipeline(prompt=case.prompt, searcher=level0_searcher)

    assert result.solver == case.expected_solver
    assert result.selected_case == case.expected_case


@pytest.mark.integration
@pytest.mark.parametrize("case", ORACLE_EXTENDED_XFAIL_CASES, ids=lambda c: c.id)
def test_oracle_extended_infrastructure_backlog(case: OracleRouteCase, level0_searcher: Level0Searcher) -> None:
    """Infrastructure-dependent oracle cases remain xfail until L2 catalogs are present."""
    pytest.xfail(case.xfail_reason)


@pytest.mark.integration
def test_oracle_gate_distribution_is_balanced() -> None:
    """Gate set keeps easy/medium/hard balance for anti-overfit coverage."""
    counts = {"easy": 0, "medium": 0, "hard": 0}
    for case in ORACLE_GATE_CASES:
        counts[case.difficulty] = counts.get(case.difficulty, 0) + 1

    assert counts["easy"] == 8
    assert counts["medium"] == 8
    assert counts["hard"] == 4
    assert len(ORACLE_GATE_CASES) == 20


@pytest.mark.integration
def test_oracle_gate_benchmark_alignment_contract() -> None:
    """
    Keep benchmark/cases YAML as the primary source of truth for gate cases.

    Any non-benchmark-backed gate case must be explicit and justified (e.g.,
    AMReX case missing from benchmark catalog, ERF special routing targets,
    or infrastructure-limited xfail coverage).
    """
    non_benchmark_ids = {case.id for case in _nonbenchmark_gate_cases(ORACLE_GATE_CASES)}
    assert non_benchmark_ids == {
        "oracle_easy_amrex_advection_amrcore",
        "oracle_easy_erf_bubble",
        "oracle_easy_erf_squallline_2d",
        "oracle_hard_incflo_benchmark_godunov",
        "oracle_hard_warpx_laser_acceleration",
    }

    benchmark_backed = _benchmark_backed_gate_cases(ORACLE_GATE_CASES)
    assert len(benchmark_backed) >= 13
    assert len({case.expected_solver for case in benchmark_backed}) >= 4


@pytest.mark.integration
def test_squall_line_schema_valid(tmp_path: Path) -> None:
    """Generated inputs file passes schema validation."""
    schema_path = Path("benchmark/specs/case_schema.yaml")
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    squall_suite = {
        "schema_version": "1.0",
        "suite_id": "oracle_squall_line_gate",
        "solver": "ERF",
        "cases": [
            {
                "id": "erf_squall_line_oracle",
                "solver": "ERF",
                "case_name": "SquallLineWarmBubble",
                "case_dir": "Exec/Convection/SquallLine",
                "inputs": "inputs_squall_line",
                "description": (
                    "Mesoscale squall line convection in ERF with warm-bubble "
                    "triggering and cloud microphysics."
                ),
                "dimension": 3,
                "physics": ["mesoscale", "convection", "warm_bubble", "microphysics"],
                "difficulty_tier": "hard",
                "prompt_length_band": "medium",
                "concept_density": "high",
                "specialized_knowledge": True,
                "novelty_tier": "config-extension",
                "scaling": {
                    "type": "strong",
                    "sizes": [
                        {
                            "label": "S",
                            "grid": "128x128x64",
                            "amr_levels": 0,
                        }
                    ],
                },
                "tags": ["oracle", "squall_line", "erf"],
                "status": "ready",
            }
        ],
    }

    suite_path = cases_dir / "erf_squall_line.yaml"
    suite_path.write_text(yaml.safe_dump(squall_suite, sort_keys=False), encoding="utf-8")

    errors = validate_case_files(schema_path=schema_path, cases_dir=cases_dir)

    assert errors == []


@pytest.mark.integration
def test_squall_line_jsonl_fields_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B3 fields present in benchmark output for squall-line case."""

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "job_status": "ok",
                    "selected_case": "erf_squall_line_oracle",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("src.benchmark_runner.subprocess.run", fake_run)

    config = {
        "prompts": [
            {
                "id": "squall_line",
                "prompt": "Run an ERF squall line case with warm bubble and cloud microphysics.",
                "solver": "ERF",
                "case_id": "erf_squall_line_oracle",
            }
        ],
        "models": [
            {
                "id": "gate_model",
                "overrides": {
                    "llm_provider": "cborg",
                    "llm_model": "mock",
                },
            }
        ],
        "run_args": {"dry_run": True},
    }
    config_path = tmp_path / "bench.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = run_model_benchmark(config_path=config_path, output_dir=tmp_path, run_name="squall_gate")

    jsonl_path = Path(result["run_dir"]) / "benchmark_runs.jsonl"
    record = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])

    required_fields = {
        "model_id",
        "prompt_id",
        "job_status",
        "analysis_status",
        "analysis_performance",
        "analysis_issues",
        "run_directory",
        "selected_case",
        "started_at",
        "ended_at",
        "duration_seconds",
        "exit_code",
        "error",
        "stderr_excerpt",
    }
    assert required_fields.issubset(record.keys())
    assert record["prompt_id"] == "squall_line"
    assert record["selected_case"] == "erf_squall_line_oracle"


@pytest.mark.integration
def test_squall_line_no_level0_regression(level0_searcher: Level0Searcher) -> None:
    """Existing Level-0 oracle prompts remain stable after routing metadata updates."""
    prompts = _load_level0_oracle_cases()

    misses: list[tuple[str, str, str]] = []
    for item in prompts:
        result = level0_searcher.search(item["prompt"], top_k=1)
        assert result, f"No Level-0 result for oracle case {item['id']}"
        got = result[0]["code"]
        expected = item["expected_solver"]
        if got != expected:
            misses.append((item["id"], expected, got))

    assert not misses, f"Level-0 oracle regressions detected: {misses}"


@pytest.mark.integration
def test_level0_index_growth_accuracy_drift_control(level0_searcher: Level0Searcher) -> None:
    """
    Enforce index-growth drift gate:
    100+ index growth must keep routing accuracy within 2% of baseline.
    """
    baseline_prompts = _load_level0_oracle_cases()
    baseline_accuracy = _oracle_solver_accuracy(level0_searcher, baseline_prompts)

    growth_prompts = (baseline_prompts * ((100 // len(baseline_prompts)) + 1))[:100]
    growth_accuracy = _oracle_solver_accuracy(level0_searcher, growth_prompts)

    verdict = level0_searcher.evaluate_index_growth_accuracy_drift(
        baseline_accuracy=baseline_accuracy,
        current_accuracy=growth_accuracy,
        index_count=len(growth_prompts),
    )

    assert verdict["gate_active"] is True
    assert verdict["accuracy_drop"] <= 0.02
    assert verdict["passed"] is True
