#!/usr/bin/env python3
"""
Test LangGraph Streaming - Incremental Step 1.

Goal: Verify we can stream workflow execution and track each node.

What this tests:
1. Create LangGraph app from existing workflow
2. Stream execution step-by-step
3. Extract node name, state, and results from each step
4. Track routing decisions
5. Measure node execution time

Success criteria:
- See each node execute in sequence
- Capture node outputs
- Identify router decisions
- Get timing data
"""

import sys
import time
from pathlib import Path

try:
    from src.config import load_config
    from src.main import create_amrex_agent_graph
except ModuleNotFoundError:
    # Add amrex_agent to path
    PELE_AGENT_ROOT = Path(__file__).parent
    sys.path.insert(0, str(PELE_AGENT_ROOT))
    from src.config import load_config
    from src.main import create_amrex_agent_graph


def test_basic_streaming():
    """Test 1: Stream the workflow."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Streaming")
    print("=" * 80)

    print("\n[1.1] Loading config...")
    config = load_config()
    print("✓ Config loaded")

    print("\n[1.2] Creating LangGraph workflow...")
    workflow = create_amrex_agent_graph()
    print("✓ Workflow created")

    print("\n[1.3] Compiling workflow...")
    app = workflow.compile()
    print("✓ Workflow compiled")

    # Simple test prompt
    test_prompt = "2D hydrogen flame with 128x128 grid, AMR with 2 levels, CFL=0.3"

    print(f"\n[1.4] Test prompt: {test_prompt}")

    # Create initial state
    # Create initial state with Phase 2 fields
    initial_state = {
        "config": config,
        "user_requirement": test_prompt,

        # Legacy fields
        "history": [],
        "loop_count": 0,
        "mode": "initial",

        # Phase 2: Iteration tracking
        "iteration": 0,
        "max_iterations": 3,
        "phase": "planning",

        # Phase 2: Error tracking
        "errors_found": [],
        "errors_fixed": [],
        "errors_active": [],

        # Phase 2: Workflow history
        "workflow_history": []
    }

    print("\n[1.5] Streaming workflow execution...")
    print("─" * 80)

    step_count = 0
    try:
        # Stream the workflow
        for event in app.stream(initial_state):
            step_count += 1
            print(f"\nStep {step_count}:")
            print(f"  Event type: {type(event)}")
            print(f"  Event keys: {event.keys() if isinstance(event, dict) else 'N/A'}")

            # Try to extract useful info
            if isinstance(event, dict):
                for key, value in event.items():
                    print(f"  {key}: {type(value)}")
                    if isinstance(value, dict):
                        # Show some state fields
                        if 'history' in value:
                            print(f"    - history length: {len(value['history'])}")
                        if 'loop_count' in value:
                            print(f"    - loop_count: {value['loop_count']}")

            if step_count > 10:  # Safety limit for testing
                print("\n⚠️  Stopping after 10 steps (safety limit)")
                break

        print("\n" + "─" * 80)
        print(f"✓ Streaming completed: {step_count} steps")

    except Exception as e:
        print(f"\n✗ Streaming failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_node_identification():
    """Test 2: Identify which node is executing."""
    print("\n" + "=" * 80)
    print("TEST 2: Node Identification")
    print("=" * 80)

    config = load_config()
    workflow = create_amrex_agent_graph()
    app = workflow.compile()

    test_prompt = "Simple hydrogen flame simulation"

    # Create initial state with Phase 2 fields
    initial_state = {
        "config": config,
        "user_requirement": test_prompt,

        # Legacy fields
        "history": [],
        "loop_count": 0,
        "mode": "initial",

        # Phase 2: Iteration tracking
        "iteration": 0,
        "max_iterations": 3,
        "phase": "planning",

        # Phase 2: Error tracking
        "errors_found": [],
        "errors_fixed": [],
        "errors_active": [],

        # Phase 2: Workflow history
        "workflow_history": []
    }

    print("\n[2.1] Attempting to identify nodes from stream...")
    print("─" * 80)

    nodes_seen = []

    try:
        for event in app.stream(initial_state):
            # LangGraph stream events are dicts with node names as keys
            if isinstance(event, dict):
                for node_name in event:
                    if node_name not in ['__start__', '__end__']:
                        nodes_seen.append(node_name)
                        print(f"\n✓ Node executed: {node_name}")

                        # Try to get the node's output
                        node_output = event[node_name]
                        if isinstance(node_output, dict):
                            # Show what the node added/modified
                            print(f"  Output keys: {list(node_output.keys())[:5]}...")  # First 5

            if len(nodes_seen) > 10:
                print("\n⚠️  Stopping after 10 nodes")
                break

        print("\n" + "─" * 80)
        print(f"✓ Identified {len(nodes_seen)} nodes:")
        for i, node in enumerate(nodes_seen, 1):
            print(f"  {i}. {node}")

        return len(nodes_seen) > 0

    except Exception as e:
        print(f"\n✗ Node identification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_timing_tracking():
    """Test 3: Measure node execution time."""
    print("\n" + "=" * 80)
    print("TEST 3: Timing Tracking")
    print("=" * 80)

    config = load_config()
    workflow = create_amrex_agent_graph()
    app = workflow.compile()

    test_prompt = "2D flame test"

    # Create initial state with Phase 2 fields
    initial_state = {
        "config": config,
        "user_requirement": test_prompt,

        # Legacy fields
        "history": [],
        "loop_count": 0,
        "mode": "initial",

        # Phase 2: Iteration tracking
        "iteration": 0,
        "max_iterations": 3,
        "phase": "planning",

        # Phase 2: Error tracking
        "errors_found": [],
        "errors_fixed": [],
        "errors_active": [],

        # Phase 2: Workflow history
        "workflow_history": []
    }

    print("\n[3.1] Tracking node execution times...")
    print("─" * 80)

    node_timings = {}
    current_node = None
    node_start = None

    try:
        workflow_start = time.time()

        for event in app.stream(initial_state):
            if isinstance(event, dict):
                for node_name in event:
                    if node_name not in ['__start__', '__end__']:
                        # End previous node timing
                        if current_node and node_start:
                            duration = time.time() - node_start
                            node_timings[current_node] = duration
                            print(f"\n✓ {current_node}: {duration:.3f}s")

                        # Start new node timing
                        current_node = node_name
                        node_start = time.time()

            if len(node_timings) > 10:
                break

        # Final node
        if current_node and node_start:
            duration = time.time() - node_start
            node_timings[current_node] = duration
            print(f"\n✓ {current_node}: {duration:.3f}s")

        total_time = time.time() - workflow_start

        print("\n" + "─" * 80)
        print(f"Total workflow time: {total_time:.3f}s")
        print("\nNode breakdown:")
        for node, duration in node_timings.items():
            percentage = (duration / total_time) * 100
            print(f"  {node:<20} {duration:>6.3f}s ({percentage:>5.1f}%)")

        return len(node_timings) > 0

    except Exception as e:
        print(f"\n✗ Timing tracking failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_extraction():
    """Test 4: Extract useful state information."""
    print("\n" + "=" * 80)
    print("TEST 4: State Extraction")
    print("=" * 80)

    config = load_config()
    workflow = create_amrex_agent_graph()
    app = workflow.compile()

    test_prompt = "Hydrogen combustion test"

    # Create initial state with Phase 2 fields
    initial_state = {
        "config": config,
        "user_requirement": test_prompt,

        # Legacy fields
        "history": [],
        "loop_count": 0,
        "mode": "initial",

        # Phase 2: Iteration tracking
        "iteration": 0,
        "max_iterations": 3,
        "phase": "planning",

        # Phase 2: Error tracking
        "errors_found": [],
        "errors_fixed": [],
        "errors_active": [],

        # Phase 2: Workflow history
        "workflow_history": []
    }

    print("\n[4.1] Extracting state information from each node...")
    print("─" * 80)

    state_snapshots = []

    try:
        for event in app.stream(initial_state):
            if isinstance(event, dict):
                for node_name, node_output in event.items():
                    if node_name in ['__start__', '__end__']:
                        continue

                    snapshot = {
                        'node': node_name,
                        'fields_modified': [],
                        'history_length': 0,
                        'loop_count': 0
                    }

                    if isinstance(node_output, dict):
                        # What fields did this node modify?
                        snapshot['fields_modified'] = list(node_output.keys())

                        # Extract interesting state
                        if 'history' in node_output:
                            snapshot['history_length'] = len(node_output['history'])
                        if 'loop_count' in node_output:
                            snapshot['loop_count'] = node_output['loop_count']
                        if 'baseline' in node_output:
                            baseline = node_output['baseline']
                            if isinstance(baseline, dict):
                                snapshot['baseline_selected'] = baseline.get('name', 'Unknown')
                        if 'review_analysis' in node_output:
                            review = node_output['review_analysis']
                            if isinstance(review, dict):
                                snapshot['review_approved'] = review.get('approved', False)

                    state_snapshots.append(snapshot)

                    print(f"\n✓ {node_name}")
                    print(f"  Modified: {', '.join(snapshot['fields_modified'][:5])}")
                    if 'baseline_selected' in snapshot:
                        print(f"  Baseline: {snapshot['baseline_selected']}")
                    if 'review_approved' in snapshot:
                        print(f"  Review: {'✓ Approved' if snapshot['review_approved'] else '✗ Rejected'}")

            if len(state_snapshots) > 10:
                break

        print("\n" + "─" * 80)
        print(f"✓ Extracted state from {len(state_snapshots)} nodes")

        return len(state_snapshots) > 0

    except Exception as e:
        print(f"\n✗ State extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all streaming tests incrementally."""
    print("\n" + "═" * 80)
    print("LANGGRAPH STREAMING TESTS - Incremental Step 1")
    print("═" * 80)
    print("\nGoal: Verify we can stream and track workflow execution")

    tests = [
        ("Basic Streaming", test_basic_streaming),
        ("Node Identification", test_node_identification),
        ("Timing Tracking", test_timing_tracking),
        ("State Extraction", test_state_extraction),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = "✓ PASS" if success else "✗ FAIL"
        except Exception as e:
            results[test_name] = f"✗ ERROR: {e}"
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "═" * 80)
    print("TEST SUMMARY")
    print("═" * 80)

    for test_name, result in results.items():
        print(f"{test_name:<30} {result}")

    passed = sum(1 for r in results.values() if "PASS" in r)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✅ All tests passed! LangGraph streaming working.")
        print("\nNext step: Build workflow tracker on top of streaming")
    else:
        print("\n⚠️  Some tests failed. Need to debug streaming integration.")


if __name__ == "__main__":
    main()
