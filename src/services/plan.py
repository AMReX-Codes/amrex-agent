"""
Simulation plan objects for AMReX Agent.

Provides typed dataclass for simulation configuration plans with factory methods
for creation and serialization. Used internally by services, converted to/from
dicts at node boundaries for LangGraph state compatibility.

Usage:
    # In architect.py (service layer)
    plan = SimulationPlanFactory.create_from_rag(...)
    return plan  # SimulationPlan object

    # In architect_node.py (node boundary)
    plan_obj = architect.execute_planning(prompt)
    state['plan'] = plan_obj.to_dict()  # Store dict in state

    # In reviewer_node.py (consumer)
    plan = SimulationPlanFactory.from_dict(state['plan'])
    confidence = plan.get_overall_confidence()
"""

import ast
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

GLOBAL_FUNCTION_COMPLEXITY_ID = "global_function_complexity"
GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD = 10
AMENDMENT_MODULE_LOC_ID = "UNNUMBERED-003-01"
AMENDMENT_MODULE_MAX_LOC = 100
UNNUMBERED_024_ID = "UNNUMBERED-024"
UNNUMBERED_052_ID = "UNNUMBERED-052"
UNNUMBERED_094_ID = "UNNUMBERED-094"


class SimulationPlan(BaseModel):
    """
    Typed simulation configuration plan.

    Tracks confidence at each decision level:
    - solver_confidence: Level 0 (code selection among configured solvers)
    - baseline_confidence: Level 2 (case selection: which example)
    - cbr_confidence: Level 3 (modification extraction quality)

    Reference: PRD Section 12.2.3
    """

    # === Core Fields (Required) ===
    selected_solver: str                    # AMReX application code name
    selected_case: str                      # Case path: "Exec/<problem_directory>"
    modifications: list[tuple[str, Any]]    # [(param, value), ...]
    reasoning: str                          # Human-readable explanation

    # === Confidence Metrics (Required per PRD 12.2.3) ===
    solver_confidence: float = 0.0          # L0: Confidence in solver choice
    baseline_confidence: float = 0.5        # L2: Confidence in baseline selection
    cbr_confidence: float = 0.0             # L3: Confidence in CBR modifications

    # === Context & Debug (Optional) ===
    prompt: str | None = None                        # Original user request
    requirements: dict[str, Any] | None = None       # Extracted requirements
    baseline: dict[str, Any] | None = None           # Baseline case metadata

    # === Traceability ===
    case_candidates: list[dict[str, Any]] | None = None      # Top-k candidates
    documentation_context: list[dict[str, Any]] | None = None  # RAG docs

    # === Phase 4 Integrations ===
    visualization: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None

    # === Parameter Resolution Feedback (populated by input_writer) ===
    unresolved_parameters: list[tuple[str, str]] | None = None  # [(requested_name, value), ...]
    suggested_mappings: dict[str, str] | None = None            # {requested: schema_param}
    resolution_guidance: str | None = None                      # For architect re-reasoning
    requires_parameter_resolution: bool = False                    # Flag for reviewer routing
    available_schema_params: list[str] | None = None         # Valid schema params from validator

    # === Solver Selection Trace (Level-0 / Level-2 override observability) ===
    level0_solver: str | None = None
    level0_confidence: float | None = None
    level2_override_applied: bool = False
    level2_override_solver: str | None = None
    level2_override_case: str | None = None
    level2_override_confidence: float | None = None

    # === Metadata ===
    used_llm: bool = False                  # Whether LLM was used for generation
    indexing_strategy: str = "simple"       # "simple", "hierarchical", or "override_static"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dict for state storage.

        Returns dict compatible with GraphState schema.
        """
        return self.model_dump()

    def to_json(self, indent: int = 2) -> str:
        """
        Serialize to JSON string.

        Parameters
        ----------
        indent : int, optional
            JSON indentation level.

        Returns
        -------
        str
            JSON-encoded plan.
        """
        return self.model_dump_json(indent=indent)

    def get_overall_confidence(self) -> float:
        """
        Compute aggregate confidence across all decision levels.

        Weighted average:
        - Solver: 20% (critical but usually high confidence)
        - Baseline: 50% (most important decision)
        - CBR: 30% (quality of modifications)

        Returns
        -------
            Float in [0.0, 1.0] representing overall plan quality
        """
        return (
            0.20 * self.solver_confidence +
            0.50 * self.baseline_confidence +
            0.30 * self.cbr_confidence
        )

    def get_summary(self) -> str:
        """
        Get human-readable summary of the plan.

        Returns
        -------
            Multi-line string with key plan details
        """
        lines = [
            "Simulation Plan Summary",
            "=" * 50,
            f"Solver: {self.selected_solver}",
            f"Baseline: {self.selected_case}",
            f"Modifications: {len(self.modifications)}",
            f"Strategy: {self.indexing_strategy}",
            f"Used LLM: {self.used_llm}",
            "",
            "Confidence Scores:",
            f"  Solver:   {self.solver_confidence:.2%}",
            f"  Baseline: {self.baseline_confidence:.2%}",
            f"  CBR:      {self.cbr_confidence:.2%}",
            f"  Overall:  {self.get_overall_confidence():.2%}",
            "",
            f"Reasoning: {self.reasoning[:200]}{'...' if len(self.reasoning) > 200 else ''}"
        ]
        return "\n".join(lines)


class SimulationPlanFactory:
    """
    Factory for creating SimulationPlan objects.

    Handles validation, normalization, and version migration.
    Provides separate creation methods for different pipeline paths.
    """

    @staticmethod
    def create_from_rag(
        solver_name: str,
        baseline_result: dict,
        cbr_plan: dict,
        docs: list,
        user_prompt: str,
        solver_confidence: float = 1.0,
        used_llm: bool = False
    ) -> SimulationPlan:
        """
        Create plan from RAG (hierarchical) pipeline outputs.

        Parameters
        ----------
        solver_name : str
            Selected solver (from L0).
        baseline_result : dict
            Baseline selection result (from L2).
        cbr_plan : dict
            CBR modification plan (from L3).
        docs : list
            Retrieved documentation (from L1).
        user_prompt : str
            Original user request.
        solver_confidence : float, optional
            L0 confidence score.
        used_llm : bool, optional
            Whether LLM was used for modifications.

        Returns
        -------
        SimulationPlan
            Constructed plan.
        """
        # Validate inputs
        if not baseline_result:
            raise ValueError("baseline_result is required")

        # Extract baseline case
        baseline_case = baseline_result.get('selected_case', {})
        baseline_conf = baseline_result.get('confidence', 0.0)

        # Extract modifications
        modifications = cbr_plan.get('modifications', [])

        # Validate modification format
        if not all(isinstance(m, tuple) and len(m) == 2 for m in modifications):
            logger.warning("Modifications not in (param, value) tuple format, attempting conversion")
            # Try to convert if they're dicts
            if modifications and isinstance(modifications[0], dict):
                modifications = [(m.get('parameter', ''), m.get('value', ''))
                               for m in modifications]

        # Extract CBR confidence
        cbr_conf = cbr_plan.get('confidence', 0.0)

        # Build reasoning
        reasoning = cbr_plan.get('reasoning', '')
        if not reasoning:
            similar_cases = cbr_plan.get('similar_cases', [])
            case_name = baseline_case.get('case', 'baseline')
            reasoning = f"CBR plan based on {case_name}"
            if similar_cases:
                reasoning += f" (patterns from: {', '.join(similar_cases[:3])})"

        return SimulationPlan(
            selected_solver=solver_name,
            selected_case=baseline_case.get('case',
                                           baseline_case.get('metadata', {}).get('repo_path', 'unknown')),
            modifications=modifications,
            reasoning=reasoning,

            # Confidence metrics
            solver_confidence=solver_confidence,
            baseline_confidence=baseline_conf,
            cbr_confidence=cbr_conf,

            # Context
            prompt=user_prompt,
            case_candidates=baseline_result.get('candidates', []),
            documentation_context=docs,
            baseline=baseline_case.get('metadata', {}),

            # Metadata
            used_llm=used_llm,
            indexing_strategy='hierarchical'
        )

    @staticmethod
    def create_from_simple(
        requirements: dict,
        baseline: dict,
        modifications: list,
        visualization: dict,
        analysis: dict,
        user_prompt: str,
        knowledge: dict | None = None
    ) -> SimulationPlan:
        """
        Create plan from simple (legacy 5-bucket) pipeline outputs.

        Parameters
        ----------
        requirements : dict
            Extracted requirements dict.
        baseline : dict
            Selected baseline case dict.
        modifications : list
            List of (param, value) tuples.
        visualization : dict
            Visualization config dict.
        analysis : dict
            Analysis config dict.
        user_prompt : str
            Original user request.
        knowledge : dict or None, optional
            Optional knowledge base items.

        Returns
        -------
        SimulationPlan
            Constructed plan.
        """
        # Extract solver
        solver = baseline.get('code') or baseline.get('code_name') or requirements.get('solver')
        if not solver:
            raise ValueError("Cannot create plan: missing solver in both requirements and baseline")

        # Extract case path
        case_path = baseline.get('case_dir', baseline.get('path', 'unknown'))

        # Build reasoning
        case_name = baseline.get('name', 'unknown')
        reasoning = f"Selected baseline: {case_name}. {len(modifications)} modifications planned."
        if baseline.get('match_rationale'):
            reasoning += f" {baseline['match_rationale']}"

        # Confidence from 5-bucket scoring
        baseline_confidence = baseline.get('total_score', baseline.get('match_score', 0.5))

        return SimulationPlan(
            selected_solver=solver,
            selected_case=case_path,
            modifications=modifications,
            reasoning=reasoning,

            # Confidence metrics (legacy path has lower CBR confidence)
            solver_confidence=0.8,  # Heuristic-based
            baseline_confidence=baseline_confidence,
            cbr_confidence=1.0 if modifications else 0.0,

            # Context
            prompt=user_prompt,
            requirements=requirements,
            baseline=baseline,
            visualization=visualization,
            analysis=analysis,

            # Metadata
            used_llm=False,
            indexing_strategy='simple'
        )

    @staticmethod
    def from_dict(data: dict) -> SimulationPlan:
        """
        Create SimulationPlan from dict (deserialization).

        Used by nodes to hydrate typed objects from state dicts.
        Handles backward compatibility with old dict formats.

        Parameters
        ----------
        data : dict
            Dict from state['plan'].

        Returns
        -------
        SimulationPlan
            Parsed plan instance.
        """
        # Handle legacy formats
        if 'selected_solver' not in data:
            data = SimulationPlanFactory._migrate_legacy_dict(data)

        # Filter to known fields to avoid TypeErrors
        valid_fields = {k: v for k, v in data.items() if k in SimulationPlan.model_fields}

        # Ensure modifications are tuples, not lists
        if 'modifications' in valid_fields:
            mods = valid_fields['modifications']
            if mods and isinstance(mods[0], list):
                valid_fields['modifications'] = [tuple(m) for m in mods]

        return SimulationPlan(**valid_fields)

    @staticmethod
    def _migrate_legacy_dict(old_dict: dict) -> dict:
        """
        Migrate old dict format to new SimulationPlan schema.

        Handles backward compatibility with pre-SimulationPlan state dicts.

        Args:
            old_dict: Legacy plan dict

        Returns
        -------
            Normalized dict compatible with SimulationPlan
        """
        logger.debug("Migrating legacy plan dict to SimulationPlan schema")

        # Extract solver (multiple possible locations)
        solver = (old_dict.get('selected_solver') or
                 old_dict.get('solver') or
                 old_dict.get('baseline', {}).get('code'))
        if not solver:
            raise ValueError("Cannot restore plan from dict: missing solver/selected_solver field")

        # Extract case path
        case = (old_dict.get('selected_case') or
               old_dict.get('baseline', {}).get('path') or
               old_dict.get('baseline', {}).get('case_dir') or
               'unknown')

        # Extract modifications (ensure tuple format)
        mods = old_dict.get('modifications', [])
        if mods and isinstance(mods[0], dict):
            # Convert from dict format to tuple
            mods = [(m.get('parameter', ''), m.get('value', '')) for m in mods]

        return {
            'selected_solver': solver,
            'selected_case': case,
            'modifications': mods,
            'reasoning': old_dict.get('reasoning', 'Legacy plan'),
            'solver_confidence': old_dict.get('solver_confidence', 0.8),
            'baseline_confidence': old_dict.get('baseline_confidence', 0.5),
            'cbr_confidence': old_dict.get('cbr_confidence', 0.5),
            'prompt': old_dict.get('prompt'),
            'requirements': old_dict.get('requirements'),
            'baseline': old_dict.get('baseline'),
            'visualization': old_dict.get('visualization'),
            'analysis': old_dict.get('analysis'),
            'used_llm': old_dict.get('used_llm', False),
            'indexing_strategy': old_dict.get('indexing_strategy', 'simple')
        }


_CYCLOMATIC_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
    ast.IfExp,
    ast.BoolOp,
    ast.Match,
)


def _cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, ast.BoolOp):
            complexity += max(0, len(child.values) - 1)
            continue
        if isinstance(child, _CYCLOMATIC_NODES):
            complexity += 1
    return complexity


def build_global_complexity_report(
    module_source: str,
    threshold: int = GLOBAL_FUNCTION_COMPLEXITY_DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """
    Build a per-function complexity report from Python source text.

    Returns a dict that can be persisted on graph state under
    ``global_complexity_report``.
    """
    tree = ast.parse(module_source)
    functions: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            score = _cyclomatic_complexity(node)
            functions.append(
                {
                    "name": node.name,
                    "lineno": node.lineno,
                    "complexity": score,
                    "threshold": threshold,
                    "passes": score <= threshold,
                }
            )

    violations = [
        function for function in functions if function["complexity"] > function["threshold"]
    ]
    return {
        "criterion": GLOBAL_FUNCTION_COMPLEXITY_ID,
        "threshold": threshold,
        "functions": functions,
        "violations": violations,
        "passes": not violations,
    }


def global_function_complexity_passed(state: dict[str, Any]) -> bool:
    """Return whether global complexity criterion is satisfied."""
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            details = approval.get("details")
            if not isinstance(details, dict):
                continue
            if details.get("criterion") != GLOBAL_FUNCTION_COMPLEXITY_ID:
                continue
            return approval.get("decision") == "approved"

    report = state.get("global_complexity_report")
    if isinstance(report, dict):
        if isinstance(report.get("passes"), bool):
            return report["passes"]
        violations = report.get("violations", [])
        if isinstance(violations, list):
            return len(violations) == 0
    return False


def global_function_complexity_failure_reason(state: dict[str, Any]) -> str:
    """Return reason code for global complexity gate decision."""
    if global_function_complexity_passed(state):
        return "global_function_complexity_satisfied"
    return "global_function_complexity_threshold_exceeded"


def _amendment_modules_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    modules = report.get("modules", [])
    if not isinstance(modules, list):
        return []

    amendment_modules: list[dict[str, Any]] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        if module.get("is_amendment_module") is True:
            amendment_modules.append(module)
    return amendment_modules


def normalize_unnumbered_024(raw: Any) -> list[dict[str, Any]]:
    """
    Normalize use-case artifact mappings into a canonical shape.

    Canonical entry:
    - use_case: str
    - artifacts: list[str]
    """
    if isinstance(raw, dict):
        for key in ("use_cases", "mappings", "entries", "items"):
            candidate = raw.get(key)
            if isinstance(candidate, list):
                raw = candidate
                break
        else:
            raw = [raw]

    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue

        use_case = entry.get("use_case") or entry.get("usecase") or entry.get("id")
        if not isinstance(use_case, str) or not use_case.strip():
            continue

        artifacts_raw = (
            entry.get("artifacts")
            or entry.get("artifact")
            or entry.get("references")
            or entry.get("evidence")
        )

        if isinstance(artifacts_raw, str):
            artifacts = [artifacts_raw.strip()] if artifacts_raw.strip() else []
        elif isinstance(artifacts_raw, list):
            artifacts = [
                item.strip()
                for item in artifacts_raw
                if isinstance(item, str) and item.strip()
            ]
        else:
            artifacts = []

        normalized.append(
            {
                "use_case": use_case.strip(),
                "artifacts": artifacts,
            }
        )
    return normalized


def _unnumbered_024_entries_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    mappings = report.get("use_case_artifacts")
    return normalize_unnumbered_024(mappings)


def _unnumbered_024_entries_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    mappings = state.get("use_case_artifacts")
    return normalize_unnumbered_024(mappings)


def normalize_unnumbered_052(raw: Any) -> list[dict[str, Any]]:
    """Normalize implementation-location to tests mappings into a canonical shape."""
    if isinstance(raw, dict):
        for key in ("feature_mappings", "feature_blocks", "features", "entries", "items"):
            candidate = raw.get(key)
            if isinstance(candidate, list):
                raw = candidate
                break
        else:
            raw = [raw]

    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue

        feature_id = entry.get("feature_id") or entry.get("feature") or entry.get("id")
        if not isinstance(feature_id, str) or not feature_id.strip():
            continue

        impl_raw = (
            entry.get("implementation_locations")
            or entry.get("impl_locations")
            or entry.get("implementation")
            or entry.get("locations")
        )
        if isinstance(impl_raw, str):
            implementation_locations = [impl_raw.strip()] if impl_raw.strip() else []
        elif isinstance(impl_raw, list):
            implementation_locations = [
                item.strip() for item in impl_raw if isinstance(item, str) and item.strip()
            ]
        else:
            implementation_locations = []

        tests_raw = (
            entry.get("tests")
            or entry.get("test_locations")
            or entry.get("test_files")
            or entry.get("fixtures")
        )
        if isinstance(tests_raw, str):
            tests = [tests_raw.strip()] if tests_raw.strip() else []
        elif isinstance(tests_raw, list):
            tests = [item.strip() for item in tests_raw if isinstance(item, str) and item.strip()]
        else:
            tests = []

        normalized.append(
            {
                "feature_id": feature_id.strip(),
                "implementation_locations": implementation_locations,
                "tests": tests,
            }
        )
    return normalized


def normalize_unnumbered_094(raw: Any) -> list[dict[str, Any]]:
    """
    Normalize camera-ready benchmark pipeline phase mappings into canonical shape.

    Canonical entry:
    - phase_id: str
    - implementation_locations: list[str]
    - tests: list[str]
    """
    if isinstance(raw, dict):
        for key in ("pipeline_phases", "phases", "entries", "items"):
            candidate = raw.get(key)
            if isinstance(candidate, list):
                raw = candidate
                break
        else:
            raw = [raw]

    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue

        phase_id = entry.get("phase_id") or entry.get("phase") or entry.get("id")
        if not isinstance(phase_id, str) or not phase_id.strip():
            continue

        impl_raw = (
            entry.get("implementation_locations")
            or entry.get("implementation")
            or entry.get("impl_locations")
            or entry.get("locations")
        )
        if isinstance(impl_raw, str):
            implementation_locations = [impl_raw.strip()] if impl_raw.strip() else []
        elif isinstance(impl_raw, list):
            implementation_locations = [
                item.strip() for item in impl_raw if isinstance(item, str) and item.strip()
            ]
        else:
            implementation_locations = []

        tests_raw = (
            entry.get("tests")
            or entry.get("test_locations")
            or entry.get("test_files")
            or entry.get("coverage")
        )
        if isinstance(tests_raw, str):
            tests = [tests_raw.strip()] if tests_raw.strip() else []
        elif isinstance(tests_raw, list):
            tests = [item.strip() for item in tests_raw if isinstance(item, str) and item.strip()]
        else:
            tests = []

        normalized.append(
            {
                "phase_id": phase_id.strip(),
                "implementation_locations": implementation_locations,
                "tests": tests,
            }
        )
    return normalized


def _unnumbered_094_entries_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    mappings = report.get("camera_ready_pipeline")
    return normalize_unnumbered_094(mappings)


def _unnumbered_094_entries_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("camera_ready_pipeline", "benchmark_pipeline", "pipeline_phases"):
        entries = normalize_unnumbered_094(state.get(key))
        if entries:
            return entries
    return []


def _unnumbered_052_entries_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    mappings = report.get("feature_mappings")
    return normalize_unnumbered_052(mappings)


def _unnumbered_052_entries_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("feature_mappings", "feature_blocks", "implementation_test_sync"):
        entries = normalize_unnumbered_052(state.get(key))
        if entries:
            return entries
    return []


def build_unnumbered_052_report(feature_mappings: Any) -> dict[str, Any]:
    """Build synchronization report for implementation locations and tests."""
    entries = normalize_unnumbered_052(feature_mappings)
    violations: list[dict[str, Any]] = []

    for entry in entries:
        if not entry["implementation_locations"]:
            violations.append({**entry, "reason_code": "impl_locations_missing"})
            continue
        if not entry["tests"]:
            violations.append({**entry, "reason_code": "tests_missing"})

    return {
        "criterion": UNNUMBERED_052_ID,
        "feature_mappings": entries,
        "violations": violations,
        "passes": bool(entries) and not violations,
    }


def impl_locations_tests_synced_passed(state: dict[str, Any]) -> bool:
    """Return whether implementation locations and tests are in sync."""
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            details = approval.get("details")
            if not isinstance(details, dict):
                continue
            if details.get("criterion") != UNNUMBERED_052_ID:
                continue
            return approval.get("decision") == "approved"

    report = state.get("impl_locations_tests_sync_report")
    if isinstance(report, dict):
        if isinstance(report.get("passes"), bool):
            return report["passes"]
        violations = report.get("violations")
        if isinstance(violations, list):
            return len(violations) == 0
        return bool(_unnumbered_052_entries_from_report(report))

    entries = _unnumbered_052_entries_from_state(state)
    if not entries:
        return False
    return all(entry["implementation_locations"] and entry["tests"] for entry in entries)


def impl_locations_tests_synced_failure_reason(state: dict[str, Any]) -> str:
    """Return reason code for implementation-location/test synchronization gate."""
    if impl_locations_tests_synced_passed(state):
        return "impl_locations_tests_synced_satisfied"

    report = state.get("impl_locations_tests_sync_report")
    if isinstance(report, dict):
        violations = report.get("violations")
        if isinstance(violations, list):
            for violation in violations:
                if not isinstance(violation, dict):
                    continue
                reason_code = violation.get("reason_code")
                if reason_code in {"impl_locations_missing", "tests_missing"}:
                    return reason_code

    entries = _unnumbered_052_entries_from_state(state)
    if not entries:
        return "impl_tests_sync_missing"

    for entry in entries:
        if not entry["implementation_locations"]:
            return "impl_locations_missing"
        if not entry["tests"]:
            return "tests_missing"

    return "impl_tests_sync_missing"


def build_amendment_module_loc_report(
    modules: list[dict[str, Any]],
    max_loc: int = AMENDMENT_MODULE_MAX_LOC,
) -> dict[str, Any]:
    """
    Build a report for amendment modules requiring helper extraction above a LOC cap.

    ``modules`` entries should include:
    - name (str)
    - loc (int)
    - is_amendment_module (bool)
    - helper_extraction_documented (bool)
    """
    normalized_modules = [module for module in modules if isinstance(module, dict)]
    violating_modules: list[dict[str, Any]] = []

    for module in normalized_modules:
        if module.get("is_amendment_module") is not True:
            continue

        loc = module.get("loc")
        if not isinstance(loc, int):
            violating_modules.append(module)
            continue

        if loc <= max_loc:
            continue

        if module.get("helper_extraction_documented") is not True:
            violating_modules.append(module)

    return {
        "criterion": AMENDMENT_MODULE_LOC_ID,
        "max_loc": max_loc,
        "modules": normalized_modules,
        "violations": violating_modules,
        "passes": not violating_modules,
    }


def amendment_module_loc_passed(state: dict[str, Any]) -> bool:
    """Return whether amendment module LOC/helper extraction criterion is satisfied."""
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            details = approval.get("details")
            if not isinstance(details, dict):
                continue
            if details.get("criterion") != AMENDMENT_MODULE_LOC_ID:
                continue
            return approval.get("decision") == "approved"

    report = state.get("amendment_module_loc_report")
    if isinstance(report, dict):
        if isinstance(report.get("passes"), bool):
            return report["passes"]
        violations = report.get("violations")
        if isinstance(violations, list):
            return len(violations) == 0
        return len(_amendment_modules_from_report(report)) == 0
    return False


def amendment_module_loc_failure_reason(state: dict[str, Any]) -> str:
    """Return reason code for amendment module LOC/helper extraction gate decision."""
    if amendment_module_loc_passed(state):
        return "amendment_module_loc_satisfied"
    return "amendment_module_helper_extraction_missing"
