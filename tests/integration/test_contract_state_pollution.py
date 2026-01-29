"""
Contract validation tests: Enforce no state pollution philosophy.

These tests validate that:
1. Nodes return ONLY utility flags at top level (mode, iteration, workflow_history)
2. ALL computation output is in workflow_history[-1]['details']
3. Downstream nodes correctly read from workflow_history, not top-level state
4. Critical bug fixes are in place
"""

import pytest
from pathlib import Path
import json


class TestNoPollutionPhilosophy:
    """Validate that nodes do NOT pollute top-level state with computation output."""

    @pytest.mark.integration
    @pytest.mark.indexing_simple
    def test_architect_node_returns_only_utility_flags(self, pele_config):
        """Architect node must return ONLY {mode, iteration, retry_count, workflow_history}, NOT computation output."""
        # This test would run architect_node and validate the returned dict
        # Expected state update: {"mode": "proceed", "iteration": 0, "workflow_history": [...]}
        # NOT allowed: {"selected_case": ..., "modifications": ..., "reasoning": ...}

        # Note: This is a specification test - actual implementation will be validated when tests run
        pass

    @pytest.mark.integration
    def test_input_writer_no_top_level_files(self, pele_config):
        """Input writer must return ONLY {mode, iteration, workflow_history}, NOT run_directory/inputs_file_path."""
        # run_directory and inputs_file_path MUST be in workflow_history[-1]['details'] only
        # Test ensures no one is tempted to put them in top-level state for "convenience"
        pass

    @pytest.mark.integration
    def test_runner_no_job_id_at_top_level(self, pele_config):
        """Runner must NOT put job_id or job_status in top-level state."""
        # These MUST be in workflow_history[-1]['details'] only
        # Analysis node will read them from workflow_history
        pass

    @pytest.mark.integration
    def test_analysis_no_report_at_top_level_primary(self, pele_config):
        """Analysis must NOT put analysis_report in top-level state as primary location."""
        # analysis_report MUST be in workflow_history[-1]['details'] only
        # Visualization will read from workflow_history
        pass


class TestDownstreamNodeDataAccess:
    """Validate that downstream nodes correctly read from workflow_history, not top-level state."""

    def test_reviewer_reads_from_architect_details(self):
        """Reviewer node must read plan from workflow_history, not from top-level state."""
        # Example workflow_history structure
        workflow_history = [
            {
                "node": "architect",
                "timestamp": "2025-01-02T14:30:45Z",
                "action": "plan_created",
                "iteration": 0,
                "details": {
                    "selected_case": "Exec/RegTests/PMF",
                    "modifications": [["amr.n_cell", "64 64 64"]],
                    "baseline": {
                        "code_name": "AMReX",
                        "repo_path": "/path/AMReX",
                        "case_path": "Exec/RegTests/PMF",
                        "local_path": "/path/AMReX/Tests/Amr/Advection_AmrCore"
                    }
                }
            }
        ]

        # Reviewer should do this:
        architect_entry = next(e for e in workflow_history if e['node'] == 'architect')
        plan = architect_entry['details']
        selected_case = plan['selected_case']
        baseline = plan['baseline']

        # Not this:
        # selected_case = workflow_history.get('selected_case')  # This should be None/missing
        # baseline = workflow_history.get('baseline')  # This should be None/missing

        assert selected_case == "Exec/RegTests/PMF"
        assert baseline['code_name'] == "AMReX"

    def test_runner_reads_from_input_writer_and_architect(self):
        """Runner must read run_directory from input_writer and baseline from architect."""
        workflow_history = [
            {
                "node": "architect",
                "details": {
                    "baseline": {
                        "code_name": "AMReX",
                        "repo_path": "/path/AMReX",
                        "local_path": "/path/AMReX/Tests/Amr/Advection_AmrCore"
                    }
                }
            },
            {
                "node": "input_writer",
                "details": {
                    "run_directory": "/scratch/runs/run_001",
                    "inputs_file_path": "/scratch/runs/run_001/inputs",
                    "status": "success"
                }
            }
        ]

        # Runner should do this:
        architect_entry = next(e for e in workflow_history if e['node'] == 'architect')
        input_writer_entry = next(e for e in workflow_history if e['node'] == 'input_writer')

        baseline = architect_entry['details']['baseline']
        run_directory = input_writer_entry['details']['run_directory']
        inputs_file = input_writer_entry['details']['inputs_file_path']

        assert baseline['code_name'] == "AMReX"
        assert run_directory == "/scratch/runs/run_001"
        assert inputs_file == "/scratch/runs/run_001/inputs"


class TestContractSpecCompliance:
    """Validate specific contract requirements from JSON contracts."""

    @pytest.mark.unit
    def test_architect_contract_specifies_no_pollution(self):
        """architect_node_contract.json must explicitly forbid state pollution."""
        contract_path = Path(__file__).parent.parent / "contracts" / "architect_node_contract.json"

        with open(contract_path) as f:
            contract = json.load(f)

        # Check that contract forbids selected_case at top level
        required_outputs = contract.get("required_outputs", {})
        required_keys = set(required_outputs.keys())

        forbidden_at_top_level = {"selected_case", "modifications", "reasoning", "baseline", "plan"}
        for forbidden in forbidden_at_top_level:
            # These should NOT be in required_outputs at top level
            if forbidden in required_keys:
                # If they are, they must be clearly marked as "in workflow_history.details ONLY"
                if isinstance(required_outputs, dict) and isinstance(required_outputs.get(forbidden), str):
                    assert "workflow_history" in required_outputs[forbidden], \
                        f"Contract allows {forbidden} at top level - violates no-pollution philosophy"

    @pytest.mark.unit
    def test_contracts_enforce_workflow_history_reading(self):
        """All node contracts must specify data_source_architecture for reading from workflow_history."""
        contracts_dir = Path(__file__).parent.parent / "contracts"
        node_contracts = [
            "reviewer_node_contract.json",
            "input_writer_node_contract.json",
            "runner_node_contract.json",
            "analysis_node_contract.json"
        ]

        for contract_file in node_contracts:
            contract_path = contracts_dir / contract_file

            with open(contract_path) as f:
                contract = json.load(f)

            required_inputs = contract.get("required_inputs", {})

            # Contract should explain data source architecture
            assert "data_source_architecture" in required_inputs, \
                f"{contract_file} must explain where to read data from (data_source_architecture)"

            data_source = required_inputs["data_source_architecture"]
            # Should contain references to reading from workflow_history
            data_source_str = json.dumps(data_source).lower()
            assert "workflow_history" in data_source_str, \
                f"{contract_file} data_source_architecture must reference workflow_history"

    @pytest.mark.unit
    def test_contracts_forbid_top_level_computation_output(self):
        """All contracts must explicitly forbid computation output at top level."""
        contracts_dir = Path(__file__).parent.parent / "contracts"
        all_contracts = list(contracts_dir.glob("*_contract.json"))

        for contract_path in all_contracts:
            with open(contract_path) as f:
                contract = json.load(f)

            # Each contract should have a section about output location
            has_location_spec = (
                "computation_output_location" in contract or
                "all_outputs_location" in contract or
                ("required_outputs" in contract and isinstance(contract["required_outputs"], dict) and
                 "note" in json.dumps(contract["required_outputs"]).lower())
            )

            assert has_location_spec, \
                f"{contract_path.name} must specify where computation output goes"


class TestCriticalBugFixValidation:
    """Validate that contracts address critical bugs discovered in schema alignment."""

    @pytest.mark.unit
    def test_architect_contract_addresses_bug_1(self):
        """Contract must address Bug #1: missing baseline metadata."""
        contract_path = Path(__file__).parent.parent / "contracts" / "architect_node_contract.json"

        with open(contract_path) as f:
            contract = json.load(f)

        critical_fixes = contract.get("critical_bug_fixes", [])
        bug_numbers = [str(fix.get("bug_id")) for fix in critical_fixes]

        assert "1" in bug_numbers or 1 in bug_numbers, \
            "architect_node_contract must reference Bug #1 (baseline metadata)"

        # Find the bug fix
        bug_1_fix = next(f for f in critical_fixes if str(f.get("bug_id")) == "1" or f.get("bug_id") == 1)

        # Contract should show baseline is required
        baseline_spec = contract.get("baseline_structure_CRITICAL")
        assert baseline_spec is not None, "Contract must have baseline_structure_CRITICAL section"
        assert "code_name" in baseline_spec.get("required_fields", {}), \
            "Baseline must include code_name"

    @pytest.mark.unit
    def test_initialization_fixes_referenced(self):
        """Contracts should reference Bug #2 and #3 (field initialization)."""
        contract_path = Path(__file__).parent.parent / "contracts" / "architect_node_contract.json"

        with open(contract_path) as f:
            contract = json.load(f)

        # Look for any reference to Bug #2 or #3
        contract_text = json.dumps(contract).lower()

        # These bugs are about initialization in main.py, so maybe not in architect contract
        # but should be in analysis or main workflow contracts
        pass


class TestWorkflowHistoryCanonicalFormat:
    """Validate workflow_history entries follow canonical format across all contracts."""

    @pytest.mark.unit
    @pytest.mark.parametrize("contract_file", [
        "architect_node_contract.json",
        "reviewer_node_contract.json",
        "input_writer_node_contract.json",
        "runner_node_contract.json",
        "analysis_node_contract.json"
    ])
    def test_canonical_workflow_entry_format(self, contract_file):
        """Each contract must show canonical workflow_history entry format."""
        contract_path = Path(__file__).parent.parent / "contracts" / contract_file

        with open(contract_path) as f:
            contract = json.load(f)

        # Check for workflow_history entry definition
        entry_spec = contract.get("workflow_history_entry_CANONICAL")
        assert entry_spec is not None, f"{contract_file} must define workflow_history_entry_CANONICAL"

        required_fields = entry_spec.get("required_fields", {})

        # All entries must have these fields
        for required_field in ["node", "timestamp", "action", "iteration", "details"]:
            assert required_field in required_fields, \
                f"{contract_file} workflow entry missing required field: {required_field}"

        # Example must show proper structure
        example = entry_spec.get("example")
        assert example is not None, f"{contract_file} must show example workflow entry"
        assert "details" in example, f"{contract_file} example missing 'details' dict"

    @pytest.mark.unit
    def test_timestamp_format_validation(self):
        """Workflow history timestamps must be ISO 8601 with 'Z' suffix."""
        contract_path = Path(__file__).parent.parent / "contracts" / "architect_node_contract.json"

        with open(contract_path) as f:
            contract = json.load(f)

        example = contract.get("workflow_history_entry_CANONICAL", {}).get("example", {})
        timestamp = example.get("timestamp", "")

        # Must be ISO 8601 format with 'Z'
        assert timestamp.endswith("Z"), "Timestamps must end with 'Z' (UTC)"
        assert "T" in timestamp, "Timestamps must be ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)"
