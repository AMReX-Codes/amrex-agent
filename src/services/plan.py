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

import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


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
        valid_fields = {
            k: v for k, v in data.items()
            if k in SimulationPlan.__dataclass_fields__
        }

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
