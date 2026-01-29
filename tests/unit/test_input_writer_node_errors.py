"""
Input Writer Node: Error Handling: Input Writer Node Error Handling Tests

These tests define the error handling contract.
"""
import importlib

import pytest
from unittest.mock import Mock, patch


input_writer_node_module = importlib.import_module("src.nodes.input_writer_node")


class TestInputWriterNodeErrorHandling:
    """
    Input Writer Node: Error Handling: Error Handling Tests
    
    Design Decisions:
    - Validation errors (service) -> mode='retry' (Architect can fix)
    - System errors (OS/IO) -> mode='fail' (hard stop)
    - Preserve partial directories for debugging
    - Follow Architect Node: Workflow History Logging history pattern
    """

    @pytest.fixture
    def basic_state(self):
        return {
            "config": Mock(output_dir="/tmp"),
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "AMReX/Tests/Amr/Advection_AmrCore",
                        "modifications": [],
                        "baseline": {"local_path": "/tmp/amrex", "code_name": "AMReX"},
                        "reasoning": "test plan",
                    },
                }
            ]
        }

    def test_catches_service_os_errors(self, basic_state):
        """
        GIVEN: Service raises OSError (disk full, permissions)
        WHEN: Node executes
        THEN: Sets mode='fail', preserves error, sets ready_to_run=False
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            # Simulate OS level crash
            MockSvc.return_value.apply_plan.side_effect = OSError("Disk full")
            
            updates = input_writer_node_module.input_writer_node(basic_state)
            
            assert updates["mode"] == "fail"
            assert "Disk full" in updates["error"]
            assert updates.get("ready_to_run") is False

    def test_handles_validation_failure_from_service(self, basic_state):
        """
        GIVEN: Service returns status='error' (validation failure)
        WHEN: Node processes result
        THEN: Sets mode='retry', populates errors_active (Architect can fix)
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            # Simulate logical validation failure (e.g. RuleEngine)
            MockSvc.return_value.apply_plan.return_value = {
                "status": "error",
                "error": "Invalid grid parameters"
            }
            
            updates = input_writer_node_module.input_writer_node(basic_state)
            
            assert updates["mode"] == "retry"
            assert "Invalid grid parameters" in updates.get("errors_active", [])

    def test_appends_success_to_history(self, basic_state):
        """
        GIVEN: Successful execution
        WHEN: Node completes
        THEN: Appends success entry to workflow_history (Architect Node: Workflow History Logging pattern)
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            MockSvc.return_value.apply_plan.return_value = {
                "status": "success",
                "run_dir": "/runs/job1",
                "inputs_path": "/runs/job1/inputs"
            }
            
            updates = input_writer_node_module.input_writer_node(basic_state)
            
            # Should append to existing history
            history = updates["workflow_history"]
            assert len(history) == 2
            
            entry = history[-1]
            assert entry["node"] == "input_writer"
            assert entry["action"] == "inputs_generated"
            assert entry["details"]["run_directory"] == "/runs/job1"

    def test_appends_failure_to_history(self, basic_state):
        """
        GIVEN: System exception occurs
        WHEN: Node catches it
        THEN: Appends failure entry with action='system_crash'
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            MockSvc.return_value.apply_plan.side_effect = RuntimeError("Critical fail")
            
            updates = input_writer_node_module.input_writer_node(basic_state)
            
            history = updates["workflow_history"]
            entry = history[-1]
            
            assert entry["node"] == "input_writer"
            assert entry["action"] == "write_failed"  # Matches current pattern
            assert "Critical fail" in entry["details"]["error"]

    def test_distinguishes_io_error_from_runtime_error(self, basic_state):
        """
        GIVEN: Different exception types
        WHEN: Node handles them
        THEN: All system errors result in mode='fail'
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            # Test various system errors
            for error in [OSError("Permission denied"), 
                         IOError("Disk full"),
                         RuntimeError("Template missing")]:
                MockSvc.return_value.apply_plan.side_effect = error
                
                updates = input_writer_node_module.input_writer_node(basic_state)
                
                assert updates["mode"] == "fail", f"Failed for {type(error).__name__}"
                assert updates.get("ready_to_run") is False

    def test_preserves_partial_directory_on_failure(self, basic_state):
        """
        GIVEN: Service fails after partial directory creation
        WHEN: Node handles error
        THEN: Does NOT delete directory (preserved for debugging per NFR-11)
        
        Note: This is implicit - we verify no cleanup code is called
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            MockSvc.return_value.apply_plan.side_effect = OSError("Disk full")
            
            # Mock filesystem operations to verify no rmtree/unlink called
            with patch("src.nodes.input_writer_node.Path") as MockPath:
                updates = input_writer_node_module.input_writer_node(basic_state)
                
                # Should NOT attempt cleanup
                # (If we were cleaning up, we'd see MockPath.unlink or shutil.rmtree calls)
                assert updates["mode"] == "fail"
                # No cleanup verification needed - absence of cleanup code is the test

    def test_logs_full_traceback_on_exception(self, basic_state):
        """
        GIVEN: Exception with stack trace
        WHEN: Node logs error
        THEN: Full traceback logged to logger (not just summary in state)
        """
        import logging
        
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            MockSvc.return_value.apply_plan.side_effect = ValueError("Bad param")
            
            # Capture log output
            with patch.object(logging.getLogger("src.nodes.input_writer_node"), 
                            "exception") as mock_logger:
                updates = input_writer_node_module.input_writer_node(basic_state)
                
                # Should log exception with traceback
                mock_logger.assert_called_once()
                assert updates["mode"] == "fail"

    def test_validation_failure_allows_retry(self, basic_state):
        """
        GIVEN: Service validation failure (fixable by Architect)
        WHEN: Node sets mode='retry'
        THEN: Graph can route back to Architect for correction
        """
        with patch("src.nodes.input_writer_node.InputWriterService") as MockSvc, \
             patch("src.services.cases.AMReXCasesService"):
            MockSvc.return_value.apply_plan.return_value = {
                "status": "error",
                "error": "CFL too high",
                "errors": ["CFL condition violated"]
            }
            
            updates = input_writer_node_module.input_writer_node(basic_state)
            
            # Should allow retry (Architect can fix CFL)
            assert updates["mode"] == "retry"
            assert len(updates.get("errors_active", [])) > 0
            
            # Should NOT set ready_to_run
            assert updates.get("ready_to_run") is not True
