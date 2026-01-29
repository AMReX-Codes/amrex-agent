# AMReXAgent Integration Test Suite


## Philosophy: "Digital Twin of Expert Workflow"

This test suite validates that the AMReXAgent correctly mimics the decision-making process of an expert computational scientist setting up AMReX simulations.

**Core Principles:**
1. **Observability**: Every decision is logged in `workflow_history`
2. **Standardization**: Follows yt-project naming conventions
3. **Determinism**: Uses immutable state updates (LangGraph Reducers Pattern)

## Integration Ladder Strategy

Tests are organized in 5 levels, each building on the previous:

### Level 1: State Machine Logic (L1) - "The Brain"
**Focus**: Planning and validation without file I/O

**Nodes Tested**: Architect, Reviewer

**Key Tests**:
- `test_l1_reflexion_loop`: Architect/Reviewer retry cycle
- `test_l1_state_transitions`: Mode transitions (initial → retry → proceed)
- `test_l1_history_tracking`: workflow_history correctness

**Mocked**: File I/O, LLM calls
**Real**: State logic, routing decisions

**Schema Focus**: `mode`, `retry_count`, `errors_active`, `workflow_history`

---

### Level 2: Filesystem I/O (L2) - "The Hands"
**Focus**: File generation and modification (Ghostwriter pattern)

**Nodes Tested**: InputWriter

**Key Tests**:
- `test_l2_ghostwriter_modification`: Preserve comments while applying changes
- `test_l2_directory_creation`: run_directory structure
- `test_l2_auxiliary_files`: Chemistry mechanisms, dat files

**Mocked**: LLM calls, Runner execution
**Real**: File creation, Load-Modify-Write pipeline

**Schema Focus**: `run_directory`, `inputs_file_path`, `script_path`

---

### Level 3: Post-Processing (L3) - "The Eyes"
**Focus**: Log parsing and artifact analysis

**Nodes Tested**: Analysis, Visualization

**Key Tests**:
- `test_l3_analysis_parsing`: Extract timesteps, CFL, metrics
- `test_l3_failure_detection`: Identify NaN, segfaults, CFL violations
- `test_l3_visualization_generation`: Plot creation (Phase 5)

**Mocked**: Runner execution (use seeded logs)
**Real**: Regex parsing, data extraction

**Schema Focus**: `analysis_report`, `visualization_images`

---

### Level 4: Execution Harness (L4) - "The Launcher"
**Focus**: Process spawning and job management

**Nodes Tested**: Runner

**Key Tests**:
- `test_l4_shim_execution`: Real subprocess using shim executable
- `test_l4_timeout_handling`: TimeoutExpired exceptions
- `test_l4_failure_exit_codes`: Non-zero exit handling

**Mocked**: Nothing (uses shim_executable fixture)
**Real**: subprocess.run, file creation by external process

**Schema Focus**: `job_id`, `job_status`, `executable_path`

**Note**: Uses `shim_executable` fixture - a Python script that mimics AMReX behavior

---

### Level 5: Full Pipeline (L5) - "The Integration"
**Focus**: End-to-end workflow validation

**Nodes Tested**: All

**Key Tests**:
- `test_l5_full_workflow_happy_path`: START → ... → END
- `test_l5_schema_validation`: GraphState compliance
- `test_l5_error_recovery`: Retry logic, max_retries enforcement
- `test_l5_cli_interface`: Argument parsing, JSON output

**Mocked**: LLM calls, heavy services (for speed)
**Real**: Graph orchestration, state flow

**Schema Focus**: Complete GraphState lifecycle

---

## Running Tests

### E2E Smoke Tests

E2E smoke tests are intentionally minimal and may be temporarily skipped during active demo refactors.
They are tagged with the `e2e` marker and can be re-enabled after demo stabilization.
They use markers like `use_real_services`, `requires_repos`, and `requires_schema` to control selection and skips.

```bash
# Run only demo e2e smoke tests
pytest -m "e2e and demo" tests/e2e/test_demo_smoke.py

# Require real services + repos + schemas
pytest -m "e2e and demo and use_real_services and requires_repos and requires_schema" tests/e2e/test_demo_smoke.py

# Run all tests except e2e
pytest -m "not e2e"
```

The e2e demo tests run validators; they will skip if required schema files
aren't available.

### By Level
```bash
# Level 1: State machine logic
pytest -m integration_l1 -v

# Level 2: Filesystem operations
pytest -m integration_l2 -v

# Level 3: Analysis/visualization
pytest -m integration_l3 -v

# Level 4: Execution (includes slow subprocess tests)
pytest -m integration_l4 -v

# Level 5: Full pipeline
pytest -m integration_full -v
```

### By Speed
```bash
# Fast tests only (no subprocess execution)
pytest tests/integration/ -m "not slow" -v

# All tests (including slow subprocess tests)
pytest tests/integration/ -v
```

### By Component
```bash
# Specific node
pytest -k "architect" -v

# Specific functionality
pytest -k "retry" -v
```

## Test Fixtures

### Shared Fixtures (tests/conftest.py)

- **`ladder_state`**: Returns appropriate state for each level
  - L1: State with plan
  - L2: State with plan + run_directory
  - L3: State with run_directory + mock outputs
  - L4: State ready for Runner

- **`shim_executable`**: Python script mimicking AMReX executable
  - Accepts `--sleep`, `--fail`, `--crash` arguments
  - Creates run.log and plt directories
  - Used for subprocess tests

- **`mock_baseline_dir`**: Temporary directory mimicking AMReX structure
  - Contains shim_executable as AMReX.ex
  - Contains inputs file
  - Used for executable discovery tests

- **`temp_repo`**: Minimal git repository structure
  - Exec/RegTests/TestCase/
  - Used for file discovery tests

### Level-Specific Fixtures

See individual test files for specialized fixtures.

## Schema Validation

All tests validate that nodes:
1. Return updates dict (not mutate state in place)
2. Use canonical field names (run_directory, not run_dir)
3. Append to workflow_history immutably

Use `src.utils.state_management.append_to_history()` helper.

## Naming Conventions (yt-project standards)

- **Variables**: Short but descriptive (`run_directory`, not `rd`)
- **Functions**: Verbs (`create_plan`, not `plan`)
- **Classes**: Nouns (`ArchitectService`, not `Architect`)
- **Constants**: UPPER_CASE (`MAX_RETRIES = 3`)

## Common Anti-Patterns to Avoid

### ❌ Mutating state in place
```python
# WRONG
state["workflow_history"].append(entry)
```

### ✅ Immutable append
```python
# CORRECT
new_history = append_to_history(
    state.get("workflow_history", []),
    node_name="architect",
    action="plan_created"
)
return {"workflow_history": new_history}
```

### ❌ Using abbreviated names
```python
# WRONG
state["run_dir"] = "/path/to/run"
```

### ✅ Full descriptive names
```python
# CORRECT
state["run_directory"] = "/path/to/run"
```

## Test Oracle (Expected Behavior)

For the prompt: **"Run a 2D premixed methane flame"**

Expected workflow_history:
```python
[
    {"node": "architect", "action": "plan_created", ...},
    {"node": "reviewer", "action": "approved", ...},
    {"node": "input_writer", "action": "files_written", ...},
    {"node": "runner", "action": "job_submitted", ...},
    {"node": "analysis", "action": "success", ...},
    {"node": "visualization", "action": "plots_generated", ...}
]
```

Final state:
- `mode`: "proceed"
- `job_status`: "completed"
- `retry_count`: 0
- `errors_active`: []

## Debugging Failed Tests

1. Check `workflow_history` to see where it diverged
2. Verify schema field names match canonical spec
3. Ensure fixtures use correct directory structure
4. Check mocks are returning expected format

## Contributing New Tests

When adding tests:
1. Place in appropriate level (L1-L5)
2. Use canonical schema field names
3. Use immutable state updates
4. Add pytest markers (`@pytest.mark.integration_lX`)
5. Update this README if adding new fixture
