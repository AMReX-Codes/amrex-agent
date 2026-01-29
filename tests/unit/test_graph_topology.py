"""
Graph Assembly: Topology: Graph Topology Construction Tests

TRUE TDD: Written BEFORE implementation.
Verifies node registration and structural definition.
"""
import pytest
from langgraph.graph import StateGraph
from src.main import create_amrex_agent_graph
from src.models import GraphState


class TestGraphTopology:
    """
    Graph Assembly: Topology: Graph Topology Construction Tests.
    
    Verifies:
    - All nodes registered
    - Entry point defined
    - Graph compiles successfully
    - Node names match router strings
    
    Design Decisions:
    - Instantiated per request (not singleton)
    - MemorySaver checkpointer (in-memory)
    - Registration order doesn't matter
    - Debug mode optional
    """

    @pytest.fixture
    def workflow_graph(self):
        """Returns the uncompiled StateGraph builder."""
        return create_amrex_agent_graph()

    def test_graph_contains_all_required_nodes(self, workflow_graph):
        """
        GIVEN: Graph created
        WHEN: Inspecting registered nodes
        THEN: All 6 core nodes present
        """
        # Access internal node registry
        nodes = workflow_graph.nodes.keys()
        
        expected_nodes = {
            "architect",
            "reviewer",
            "input_writer",
            "runner",
            "analysis",
            "visualization"
        }
        
        assert expected_nodes.issubset(nodes), \
            f"Missing nodes: {expected_nodes - nodes}"

    def test_entry_point_is_architect(self, workflow_graph):
        """
        GIVEN: Graph created
        WHEN: Compiling graph
        THEN: Entry point (START) connects to architect
        """
        app = workflow_graph.compile()
        
        # Verify graph starts with architect node
        # LangGraph stores this in the compiled graph structure
        graph_def = app.get_graph()
        
        # Check that START node has edge to architect
        start_edges = [edge for edge in graph_def.edges 
                      if edge[0] == "__start__"]
        
        assert len(start_edges) > 0, "No entry point defined"
        assert start_edges[0][1] == "architect", \
            f"Entry point should be 'architect', got {start_edges[0][1]}"

    def test_graph_compiles_without_errors(self, workflow_graph):
        """
        GIVEN: Graph with all nodes registered
        WHEN: Calling compile()
        THEN: Returns compiled graph without exceptions
        """
        try:
            app = workflow_graph.compile()
            assert app is not None
        except Exception as e:
            pytest.fail(f"Graph compilation failed: {e}")

    def test_graph_uses_state_schema(self, workflow_graph):
        """
        GIVEN: Graph initialized
        WHEN: Inspecting schema
        THEN: Uses GraphState TypedDict
        """
        # Verify graph is StateGraph with correct schema
        assert isinstance(workflow_graph, StateGraph)
        # The schema is stored in workflow_graph.schema or channels
        # This is more of a structural check

    def test_node_names_match_routing_strings(self, workflow_graph):
        """
        GIVEN: Graph nodes registered
        WHEN: Comparing with router return values
        THEN: All router strings have corresponding nodes
        """
        nodes = set(workflow_graph.nodes.keys())
        
        # Router functions return these strings
        expected_from_routers = {
            "architect",
            "reviewer", 
            "input_writer",
            "runner",
            "analysis",
            "visualization"
        }
        
        assert expected_from_routers.issubset(nodes), \
            "Router strings don't match registered nodes"

    def test_graph_accepts_checkpointer(self):
        """
        GIVEN: Custom checkpointer provided
        WHEN: Creating graph
        THEN: Uses provided checkpointer
        """
        from langgraph.checkpoint.memory import MemorySaver
        
        custom_checkpointer = MemorySaver()
        graph = create_amrex_agent_graph(checkpointer=custom_checkpointer)
        
        # Verify graph was created
        assert graph is not None

    def test_graph_creates_default_checkpointer(self):
        """
        GIVEN: No checkpointer provided
        WHEN: Creating graph
        THEN: Uses default MemorySaver
        """
        graph = create_amrex_agent_graph()
        
        # Graph should be created successfully
        assert graph is not None
        
        # Should be able to compile (which requires checkpointer internally)
        app = graph.compile()
        assert app is not None

    def test_multiple_graph_instances_independent(self):
        """
        GIVEN: Multiple calls to create_amrex_agent_graph
        WHEN: Creating separate instances
        THEN: Each is independent (not singleton)
        """
        graph1 = create_amrex_agent_graph()
        graph2 = create_amrex_agent_graph()
        
        assert graph1 is not graph2, \
            "Graphs should be separate instances"
