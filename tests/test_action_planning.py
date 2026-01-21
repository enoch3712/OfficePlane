"""
Tests for the action plan tree system.

Tests the planning module including:
- PlaceholderID parsing
- ActionNode/ActionPlan structures
- Plan visualization
- Plan generation with mock LLM
- AuthorComponent integration
"""

import pytest

from officeplane.components.planning import (
    ActionNode,
    ActionPlan,
    GeneratePlanInput,
    MockPlanLLM,
    NodeStatus,
    PlaceholderID,
    PlanDisplayer,
    PlanGenerator,
    PlanSummary,
    create_plan_from_outline,
)


class TestPlaceholderID:
    """Tests for PlaceholderID parsing and formatting."""

    def test_parse_simple(self):
        """Test parsing simple placeholder."""
        placeholder = PlaceholderID.parse("$node_doc.id")
        assert placeholder.node_id == "node_doc"
        assert placeholder.output_field == "id"

    def test_parse_default_field(self):
        """Test parsing placeholder without field defaults to id."""
        placeholder = PlaceholderID.parse("$node_ch0")
        assert placeholder.node_id == "node_ch0"
        assert placeholder.output_field == "id"

    def test_parse_with_underscores(self):
        """Test parsing placeholder with underscores in node_id."""
        placeholder = PlaceholderID.parse("$node_ch0_sec1.document_id")
        assert placeholder.node_id == "node_ch0_sec1"
        assert placeholder.output_field == "document_id"

    def test_parse_invalid_no_dollar(self):
        """Test that parsing without $ raises ValueError."""
        with pytest.raises(ValueError, match="must start with"):
            PlaceholderID.parse("node_doc.id")

    def test_str_representation(self):
        """Test string representation."""
        placeholder = PlaceholderID(node_id="node_ch0", output_field="id")
        assert str(placeholder) == "$node_ch0.id"

    def test_is_placeholder(self):
        """Test placeholder detection."""
        assert PlaceholderID.is_placeholder("$node_doc.id") is True
        assert PlaceholderID.is_placeholder("node_doc.id") is False
        assert PlaceholderID.is_placeholder(123) is False
        assert PlaceholderID.is_placeholder(None) is False


class TestActionNode:
    """Tests for ActionNode structure."""

    def test_create_node(self):
        """Test creating a simple node."""
        node = ActionNode(
            id="node_1",
            action_name="create_document",
            description="Create the document",
            inputs={"title": "My Book"},
        )
        assert node.id == "node_1"
        assert node.action_name == "create_document"
        assert node.status == NodeStatus.PENDING

    def test_node_with_placeholder_inputs(self):
        """Test node with placeholder inputs."""
        node = ActionNode(
            id="node_ch0",
            action_name="add_chapter",
            description="Add chapter",
            inputs={"document_id": "$node_doc.id", "title": "Chapter 1"},
        )
        deps = node.get_placeholder_dependencies()
        assert len(deps) == 1
        assert deps[0].node_id == "node_doc"

    def test_dependency_node_ids(self):
        """Test getting dependency node IDs."""
        node = ActionNode(
            id="node_sec",
            action_name="add_section",
            inputs={
                "chapter_id": "$node_ch0.id",
                "document_id": "$node_doc.id",
            },
        )
        dep_ids = node.get_dependency_node_ids()
        assert set(dep_ids) == {"node_ch0", "node_doc"}

    def test_node_with_children(self):
        """Test node with children."""
        child = ActionNode(id="child_1", action_name="write_page")
        parent = ActionNode(
            id="parent_1",
            action_name="add_section",
            children=[child],
        )
        assert len(parent.children) == 1
        assert parent.count_descendants() == 1

    def test_nested_descendants_count(self):
        """Test counting nested descendants."""
        grandchild = ActionNode(id="gc", action_name="write_page")
        child = ActionNode(id="c", action_name="add_section", children=[grandchild])
        parent = ActionNode(id="p", action_name="add_chapter", children=[child])

        assert parent.count_descendants() == 2
        assert child.count_descendants() == 1


class TestActionPlan:
    """Tests for ActionPlan structure."""

    def test_create_plan(self):
        """Test creating a plan."""
        doc_node = ActionNode(
            id="node_doc",
            action_name="create_document",
            inputs={"title": "Test Book"},
        )
        plan = ActionPlan(
            title="Test Book",
            original_prompt="Write a test book",
            roots=[doc_node],
        )
        assert plan.title == "Test Book"
        assert plan.total_nodes == 1
        assert plan.action_counts["create_document"] == 1

    def test_plan_with_hierarchy(self):
        """Test plan with full hierarchy."""
        page = ActionNode(id="pg", action_name="write_page", inputs={})
        section = ActionNode(id="sec", action_name="add_section", children=[page])
        chapter = ActionNode(id="ch", action_name="add_chapter", children=[section])
        doc = ActionNode(id="doc", action_name="create_document", children=[chapter])

        plan = ActionPlan(
            title="Test",
            original_prompt="Test prompt",
            roots=[doc],
        )

        assert plan.total_nodes == 4
        assert plan.action_counts["create_document"] == 1
        assert plan.action_counts["add_chapter"] == 1
        assert plan.action_counts["add_section"] == 1
        assert plan.action_counts["write_page"] == 1
        assert plan.estimated_pages == 1

    def test_get_node(self):
        """Test getting a node by ID."""
        child = ActionNode(id="child_1", action_name="add_chapter")
        root = ActionNode(id="root_1", action_name="create_document", children=[child])
        plan = ActionPlan(title="Test", original_prompt="Test", roots=[root])

        found = plan.get_node("child_1")
        assert found is not None
        assert found.id == "child_1"

        not_found = plan.get_node("nonexistent")
        assert not_found is None

    def test_execution_order(self):
        """Test topological execution order."""
        page1 = ActionNode(id="p1", action_name="write_page", order_index=0)
        page2 = ActionNode(id="p2", action_name="write_page", order_index=1)
        section = ActionNode(
            id="s", action_name="add_section", children=[page1, page2]
        )
        chapter = ActionNode(id="c", action_name="add_chapter", children=[section])
        doc = ActionNode(id="d", action_name="create_document", children=[chapter])

        plan = ActionPlan(title="Test", original_prompt="Test", roots=[doc])
        order = plan.get_execution_order()

        # Parents should come before children
        ids = [n.id for n in order]
        assert ids.index("d") < ids.index("c")
        assert ids.index("c") < ids.index("s")
        assert ids.index("s") < ids.index("p1")
        assert ids.index("s") < ids.index("p2")

    def test_to_summary(self):
        """Test plan summary generation."""
        doc = ActionNode(id="doc", action_name="create_document")
        plan = ActionPlan(
            title="Test Book",
            original_prompt="Write a test book",
            roots=[doc],
        )
        summary = plan.to_summary()

        assert summary["id"] == plan.id
        assert summary["title"] == "Test Book"
        assert summary["total_actions"] == 1


class TestPlanDisplayer:
    """Tests for plan visualization."""

    @pytest.fixture
    def sample_plan(self):
        """Create a sample plan for testing."""
        page = ActionNode(
            id="pg",
            action_name="write_page",
            description="Introduction page",
            inputs={"section_id": "$sec.id", "page_number": 1},
        )
        section = ActionNode(
            id="sec",
            action_name="add_section",
            description="Getting Started",
            inputs={"chapter_id": "$ch.id", "title": "Getting Started"},
            children=[page],
        )
        chapter = ActionNode(
            id="ch",
            action_name="add_chapter",
            description="Introduction",
            inputs={"document_id": "$doc.id", "title": "Introduction"},
            children=[section],
        )
        doc = ActionNode(
            id="doc",
            action_name="create_document",
            description="Create the book",
            inputs={"title": "Python Guide"},
            children=[chapter],
        )
        return ActionPlan(
            title="Python Guide",
            original_prompt="Write a Python programming guide",
            roots=[doc],
        )

    def test_to_tree_text(self, sample_plan):
        """Test ASCII tree generation."""
        tree = PlanDisplayer.to_tree_text(sample_plan)

        print("\n" + "=" * 70)
        print("TREE TEXT OUTPUT")
        print("=" * 70)
        print(tree)
        print("=" * 70)

        assert "Python Guide" in tree
        assert "create_document" in tree
        assert "add_chapter" in tree
        assert "add_section" in tree
        assert "write_page" in tree

    def test_to_tree_text_with_max_depth(self, sample_plan):
        """Test tree with depth limit."""
        tree = PlanDisplayer.to_tree_text(sample_plan, max_depth=1)

        assert "create_document" in tree
        assert "add_chapter" in tree
        # Should not include section/page at depth > 1
        # (depth 0 = doc, depth 1 = chapter, depth 2 = section)
        assert "add_section" not in tree

    def test_to_markdown(self, sample_plan):
        """Test markdown generation."""
        md = PlanDisplayer.to_markdown(sample_plan)

        assert "# Action Plan: Python Guide" in md
        assert "**Document:**" in md
        assert "**Chapter:**" in md
        assert "*Section:*" in md
        assert "Page:" in md

    def test_to_mermaid(self, sample_plan):
        """Test Mermaid diagram generation."""
        mermaid = PlanDisplayer.to_mermaid(sample_plan)
        mermaid_raw = PlanDisplayer.to_mermaid(sample_plan, include_fences=False)

        # Print raw mermaid (paste directly into mermaid.live)
        print("\n" + mermaid_raw)

        assert "```mermaid" in mermaid
        assert "graph TD" in mermaid
        assert "```" in mermaid
        # Check for node connections
        assert "-->" in mermaid
        # Raw version should not have fences
        assert "```" not in mermaid_raw
        assert "graph TD" in mermaid_raw

    def test_to_json(self, sample_plan):
        """Test JSON export."""
        data = PlanDisplayer.to_json(sample_plan)

        assert data["title"] == "Python Guide"
        assert "tree" in data
        assert len(data["tree"]) == 1  # One root
        assert data["tree"][0]["action"] == "create_document"
        assert "children" in data["tree"][0]

    def test_to_json_without_inputs(self, sample_plan):
        """Test JSON export without inputs."""
        data = PlanDisplayer.to_json(sample_plan, include_inputs=False)

        assert "inputs" not in data["tree"][0]

    def test_to_compact_tree(self, sample_plan):
        """Test compact tree format."""
        compact = PlanDisplayer.to_compact_tree(sample_plan)

        print("\n" + "=" * 70)
        print("COMPACT TREE OUTPUT")
        print("=" * 70)
        print(compact)
        print("=" * 70)

        assert "[D]" in compact  # Document symbol
        assert "[C]" in compact  # Chapter symbol
        assert "[S]" in compact  # Section symbol
        assert "[P]" in compact  # Page symbol


class TestPlanGenerator:
    """Tests for plan generation."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        return MockPlanLLM(num_chapters=2, num_sections=2, num_pages=1)

    @pytest.mark.asyncio
    async def test_generate_plan(self, mock_llm):
        """Test plan generation with mock LLM."""
        generator = PlanGenerator(llm=mock_llm)
        input_data = GeneratePlanInput(
            prompt="Write a book about Python programming",
            max_chapters=5,
            max_sections_per_chapter=3,
        )

        result = await generator.generate_plan(input_data)

        assert result.success is True
        assert result.error is None
        assert result.generation_time_ms >= 0
        assert result.plan.title is not None
        assert result.plan.total_nodes > 0

    @pytest.mark.asyncio
    async def test_generate_plan_structure(self, mock_llm):
        """Test generated plan has correct structure."""
        generator = PlanGenerator(llm=mock_llm)
        input_data = GeneratePlanInput(prompt="Test book")

        result = await generator.generate_plan(input_data)
        plan = result.plan

        # Should have one root (document)
        assert len(plan.roots) == 1
        doc_node = plan.roots[0]
        assert doc_node.action_name == "create_document"

        # Document should have chapter children
        assert len(doc_node.children) == 2
        for ch_node in doc_node.children:
            assert ch_node.action_name == "add_chapter"
            # Chapter should reference document via placeholder
            assert "$" in ch_node.inputs["document_id"]

    @pytest.mark.asyncio
    async def test_generate_plan_limits(self):
        """Test that limits are applied."""
        mock_llm = MockPlanLLM(num_chapters=10, num_sections=10, num_pages=5)
        generator = PlanGenerator(llm=mock_llm)

        input_data = GeneratePlanInput(
            prompt="Test",
            max_chapters=3,
            max_sections_per_chapter=2,
            max_pages_per_section=1,
        )

        result = await generator.generate_plan(input_data)
        plan = result.plan

        doc_node = plan.roots[0]
        assert len(doc_node.children) <= 3  # max_chapters

        for ch_node in doc_node.children:
            assert len(ch_node.children) <= 2  # max_sections
            for sec_node in ch_node.children:
                assert len(sec_node.children) <= 1  # max_pages

    def test_generate_plan_sync(self, mock_llm):
        """Test synchronous plan generation."""
        generator = PlanGenerator(llm=mock_llm)
        input_data = GeneratePlanInput(prompt="Test book")

        result = generator.generate_plan_sync(input_data)

        assert result.success is True
        assert result.plan.total_nodes > 0


class TestCreatePlanFromOutline:
    """Tests for programmatic plan creation."""

    def test_create_simple_plan(self):
        """Test creating a plan from outline dict."""
        chapters = [
            {
                "title": "Introduction",
                "description": "Getting started",
                "sections": [
                    {
                        "title": "Overview",
                        "description": "Overview section",
                        "pages": [
                            {"title": "Welcome", "content_outline": "Welcome to the book"},
                        ],
                    }
                ],
            }
        ]

        plan = create_plan_from_outline(
            title="My Book",
            original_prompt="Write a book",
            chapters=chapters,
        )

        assert plan.title == "My Book"
        assert plan.original_prompt == "Write a book"
        assert plan.action_counts["create_document"] == 1
        assert plan.action_counts["add_chapter"] == 1
        assert plan.action_counts["add_section"] == 1
        assert plan.action_counts["write_page"] == 1

    def test_create_plan_with_multiple_chapters(self):
        """Test creating a plan with multiple chapters."""
        chapters = [
            {"title": f"Chapter {i}", "sections": []}
            for i in range(3)
        ]

        plan = create_plan_from_outline(
            title="Multi-Chapter Book",
            original_prompt="Test",
            chapters=chapters,
        )

        assert plan.action_counts["add_chapter"] == 3


class TestPlanSummary:
    """Tests for PlanSummary model."""

    def test_from_plan(self):
        """Test creating summary from plan."""
        doc = ActionNode(id="doc", action_name="create_document")
        chapter = ActionNode(id="ch", action_name="add_chapter")
        doc.children.append(chapter)

        plan = ActionPlan(
            title="Test Book",
            original_prompt="Write a test book",
            roots=[doc],
        )

        summary = PlanSummary.from_plan(plan)

        assert summary.plan_id == plan.id
        assert summary.title == "Test Book"
        assert summary.original_prompt == "Write a test book"
        assert summary.total_actions == 2
        assert summary.chapters == 1
        assert summary.tree_visualization is not None
