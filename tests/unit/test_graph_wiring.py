"""
Graph Assembly: Conditional Wiring: Graph Conditional Wiring Tests

TRUE TDD: Written BEFORE implementation.
Verifies conditional edges and reflexion pattern support.
"""
import pytest
from unittest.mock import Mock
from langgraph.graph import StateGraph, END
from src.main import create_amrex_agent_graph


class TestGraphConditionalWiring:
    """
    Graph Assembly: Conditional Wiring: Conditional Wiring Tests.
    
    Verifies:
    - Conditional edges defined
    - Reflexion pattern (retry loops)
    - Terminal edges
    - Path completeness
    
    Design Decisions:
    - No priority order (handled by router)
    - Mermaid for visualization
    - Recursion limit for loop prevention
    - Standard add_conditional_edges API
    """

    @pytest.fixture
    def graph_builder(self):
        """Returns the uncompiled StateGraph builder."""
        return create_amrex_agent_graph()

    @pytest.fixture
    def compiled_app(self, graph_builder):
        """Returns compiled graph for structural inspection."""
        return graph_builder.compile()

    def test_reviewer_has_conditional_edges(self, compiled_app):
        """
        GIVEN: Graph with reviewer node
        WHEN: Inspecting graph structure
        THEN: Reviewer has conditional edges (not simple edge)
        """
        graph_def = compiled_app.get_graph()
        
        # Find edges from reviewer
        reviewer_edges = [edge for edge in graph_def.edges 
                         if edge[0] == "reviewer"]
        
        # Should have multiple possible destinations
        # (conditional edges show up as multiple edge entries)
        assert len(reviewer_edges) > 1, \
            "Reviewer should have conditional routing (multiple edges)"

    def test_reviewer_routes_to_input_writer_architect_or_end(self, compiled_app):
        """
        GIVEN: Graph compiled
        WHEN: Checking reviewer destinations
        THEN: Can route to input_writer, architect, or END
        """
        graph_def = compiled_app.get_graph()
        
        reviewer_edges = [edge for edge in graph_def.edges 
                         if edge[0] == "reviewer"]
        
        destinations = {edge[1] for edge in reviewer_edges}
        
        expected_destinations = {"input_writer", "architect", "__end__"}
        assert expected_destinations.issubset(destinations), \
            f"Reviewer should route to {expected_destinations}, got {destinations}"

    def test_architect_to_reviewer_edge_exists(self, compiled_app):
        """
        GIVEN: Graph with architect node
        WHEN: Checking edges
        THEN: Architect connects to reviewer
        """
        graph_def = compiled_app.get_graph()
        
        architect_edges = [edge for edge in graph_def.edges 
                          if edge[0] == "architect"]
        
        destinations = {edge[1] for edge in architect_edges}
        
        assert "reviewer" in destinations, \
            "Architect should always route to reviewer"

    def test_graph_supports_retry_cycle(self, compiled_app):
        """
        GIVEN: Graph with conditional edges
        WHEN: Checking for cycles
        THEN: reviewer→architect→reviewer path exists (reflexion loop)
        """
        graph_def = compiled_app.get_graph()
        
        # Verify reviewer can reach architect
        reviewer_edges = [edge for edge in graph_def.edges 
                         if edge[0] == "reviewer" and edge[1] == "architect"]
        assert len(reviewer_edges) > 0, "Retry loop missing: reviewer→architect"
        
        # Verify architect can reach reviewer
        architect_edges = [edge for edge in graph_def.edges 
                          if edge[0] == "architect" and edge[1] == "reviewer"]
        assert len(architect_edges) > 0, "Review flow missing: architect→reviewer"

    def test_analysis_has_conditional_edges(self, compiled_app):
        """
        GIVEN: Graph with analysis node
        WHEN: Checking edges
        THEN: Analysis has conditional routing
        """
        graph_def = compiled_app.get_graph()
        
        analysis_edges = [edge for edge in graph_def.edges 
                         if edge[0] == "analysis"]
        
        # Should have multiple destinations (success/failure paths)
        assert len(analysis_edges) > 1, \
            "Analysis should have conditional routing"

    def test_analysis_routes_to_visualization_or_reviewer(self, compiled_app):
        """
        GIVEN: Graph compiled
        WHEN: Checking analysis destinations
        THEN: Can route to visualization (success) or reviewer (failure)
        """
        graph_def = compiled_app.get_graph()
        
        analysis_edges = [edge for edge in graph_def.edges 
                         if edge[0] == "analysis"]
        
        destinations = {edge[1] for edge in analysis_edges}
        
        expected_destinations = {"visualization", "reviewer"}
        assert expected_destinations.issubset(destinations), \
            f"Analysis should route to {expected_destinations}, got {destinations}"

    def test_input_writer_to_runner_edge_exists(self, compiled_app):
        """
        GIVEN: Graph with linear execution path
        WHEN: Checking edges
        THEN: input_writer→runner edge exists
        """
        graph_def = compiled_app.get_graph()
        
        writer_edges = [edge for edge in graph_def.edges 
                       if edge[0] == "input_writer"]
        
        destinations = {edge[1] for edge in writer_edges}
        
        assert "runner" in destinations, \
            "Input writer should route to runner"

    def test_runner_to_analysis_edge_exists(self, compiled_app):
        """
        GIVEN: Graph with execution path
        WHEN: Checking edges
        THEN: runner→analysis edge exists
        """
        graph_def = compiled_app.get_graph()
        
        runner_edges = [edge for edge in graph_def.edges 
                       if edge[0] == "runner"]
        
        destinations = {edge[1] for edge in runner_edges}
        
        assert "analysis" in destinations, \
            "Runner should route to analysis"

    def test_visualization_to_end_edge_exists(self, compiled_app):
        """
        GIVEN: Graph with visualization node
        WHEN: Checking terminal edges
        THEN: visualization→END edge exists
        """
        graph_def = compiled_app.get_graph()
        
        viz_edges = [edge for edge in graph_def.edges 
                    if edge[0] == "visualization"]
        
        destinations = {edge[1] for edge in viz_edges}
        
        assert "__end__" in destinations, \
            "Visualization should route to END"

    def test_all_nodes_reachable_from_start(self, compiled_app):
        """
        GIVEN: Compiled graph
        WHEN: Traversing from START
        THEN: All nodes reachable (no orphaned nodes)
        """
        graph_def = compiled_app.get_graph()
        
        # All nodes should be in the graph
        all_nodes = set(graph_def.nodes.keys())
        
        expected_nodes = {
            "__start__", "architect", "reviewer", 
            "input_writer", "runner", "analysis", 
            "visualization", "__end__"
        }
        
        assert expected_nodes.issubset(all_nodes), \
            f"Missing nodes: {expected_nodes - all_nodes}"

    def test_graph_compiles_with_cycles(self, graph_builder):
        """
        GIVEN: Graph with conditional cycles
        WHEN: Compiling with checkpointer
        THEN: Compiles successfully (cycles allowed)
        """
        try:
            app = graph_builder.compile()
            assert app is not None
        except Exception as e:
            pytest.fail(f"Graph with cycles should compile: {e}")


class TestIntentClarificationWiring:
    @pytest.fixture
    def graph_builder(self):
        from src.graph import create_graph

        return create_graph()

    @pytest.fixture
    def compiled_app(self, graph_builder):
        return graph_builder.compile()

    def test_intent_extraction_node_in_graph(self, compiled_app):
        """
        Given: compiled graph
        When:  nodes listed
        Then:  intent_extraction_node present
        """
        graph_def = compiled_app.get_graph()
        assert "intent_extraction_node" in graph_def.nodes

    def test_clarification_node_in_graph(self, compiled_app):
        """
        Given: compiled graph
        When:  nodes listed
        Then:  clarification_node present
        """
        graph_def = compiled_app.get_graph()
        assert "clarification_node" in graph_def.nodes

    def test_clarification_handler_wired_to_schema_aware_node(self, graph_builder):
        """
        Given: graph builder internals
        When:  inspecting clarification_handler runnable binding
        Then:  it points to src.nodes.clarification_handler_node implementation
        """
        node_spec = graph_builder.nodes["clarification_handler"]
        assert node_spec.runnable.func.__module__ == "src.nodes.clarification_handler_node"
        assert node_spec.runnable.func.__name__ == "clarification_handler_node"

    def test_intent_extraction_runs_before_input_writer(self, compiled_app):
        """
        Given: graph execution order
        When:  traced from START
        Then:  intent_extraction_node appears before
               input_writer_node in reachable path
        """
        graph_def = compiled_app.get_graph()
        edges = {(edge.source, edge.target) for edge in graph_def.edges}
        assert ("architect_node", "intent_extraction_node") in edges
        assert ("intent_extraction_node", "clarification_node") in edges
        assert ("clarification_node", "input_writer_node") in edges

    def test_clarification_runs_after_intent_extraction(self, compiled_app):
        """
        Given: graph execution order
        When:  traced from intent_extraction_node
        Then:  clarification_node is next reachable node
        """
        graph_def = compiled_app.get_graph()
        edges = {(edge.source, edge.target) for edge in graph_def.edges}
        assert ("intent_extraction_node", "clarification_node") in edges

    def test_clarification_needed_false_routes_to_writer(self):
        """
        Given: state with clarification_needed = False
        When:  conditional edge from clarification_node
               evaluated
        Then:  routes to input_writer_node
        """
        from src.graph import _route_after_clarification

        assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
        assert _route_after_clarification({}) == "input_writer_node"

    def test_clarification_needed_true_routes_to_handler(self):
        """
        Given: state with clarification_needed = True
        When:  conditional edge from clarification_node
               evaluated
        Then:  routes to clarification_handler or END
               NOT to input_writer_node
        """
        from src.graph import _route_after_clarification

        route = _route_after_clarification({"clarification_needed": True})
        assert route == "clarification_handler"
        assert route != "input_writer_node"

    def test_graph_compiles_without_error(self, graph_builder):
        """
        Given: graph definition with new nodes wired
        When:  graph.compile() runs
        Then:  no exception raised
        """
        app = graph_builder.compile()
        assert app is not None


class TestSweepWiring:
    @pytest.fixture
    def graph_builder(self):
        from src.graph import create_graph

        return create_graph()

    @pytest.fixture
    def compiled_app(self, graph_builder):
        return graph_builder.compile()

    def test_sweep_detection_node_in_graph(self, compiled_app):
        """
        Given: compiled graph
        When:  nodes listed
        Then:  sweep_detection_node present
        """
        graph_def = compiled_app.get_graph()
        assert "sweep_detection_node" in graph_def.nodes

    def test_sweep_detection_runs_before_architect(self, compiled_app):
        """
        Given: graph execution order
        When:  traced from START
        Then:  sweep_detection_node appears before
               architect_node in reachable path
        Sweep must be known before Architect plans.
        """
        graph_def = compiled_app.get_graph()
        edges = {(edge.source, edge.target) for edge in graph_def.edges}
        assert ("__start__", "sweep_detection_node") in edges
        assert ("sweep_detection_node", "architect_node") in edges

    def test_no_sweep_routes_to_architect(self):
        """
        Given: state with sweep_id = None
        When:  conditional edge from
               sweep_detection_node evaluated
        Then:  routes to architect_node
        """
        from src.graph import _route_after_sweep_detection

        assert _route_after_sweep_detection({"sweep_id": None}) == "architect_node"
        assert _route_after_sweep_detection({}) == "architect_node"

    def test_sweep_detected_routes_to_sweep_handler(self):
        """
        Given: state with sweep_id set (non-None)
        When:  conditional edge from
               sweep_detection_node evaluated
        Then:  routes to sweep_execution_handler
               NOT to architect_node directly
        """
        from src.graph import _route_after_sweep_detection

        route = _route_after_sweep_detection({"sweep_id": "sweep_001"})
        assert route == "sweep_execution_handler"
        assert route != "architect_node"

    def test_graph_still_compiles_after_sweep_wiring(self, graph_builder):
        """
        Given: graph with sweep nodes wired
        When:  graph.compile() runs
        Then:  no exception raised
        """
        app = graph_builder.compile()
        assert app is not None

    def test_oracle_paths_unaffected_by_sweep_wiring(self):
        """
        Given: oracle prompts with no sweep language
        When:  sweep_detection_node evaluates them
        Then:  sweep_id remains None
               all route to architect_node
        """
        import json
        from pathlib import Path

        from src.graph import _route_after_sweep_detection
        from src.nodes.sweep_detection_node import sweep_detection_node

        prompts_path = Path(__file__).resolve().parents[1] / "data" / "level0_ab_prompts.json"
        prompts = json.loads(prompts_path.read_text(encoding="utf-8"))

        for item in prompts:
            result = sweep_detection_node({"prompt": item["prompt"]})
            assert result["sweep_id"] is None
            assert _route_after_sweep_detection(result) == "architect_node"
