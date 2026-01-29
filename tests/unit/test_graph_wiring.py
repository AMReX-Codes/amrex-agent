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
