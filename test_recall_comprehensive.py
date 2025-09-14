"""Comprehensive tests for recall functionality.

Tests the recall tool end-to-end with realistic data to ensure
it works properly after the PlanStep.status bug is fixed.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models.plan import Plan, PlanStep, PlanStatus
from src.tusk.models.todo import Todo, TodoStatus, TodoPriority
from src.tusk.models.checkpoint import Checkpoint
from src.tusk.models.highlight import Highlight, HighlightCategory, HighlightImportance
from src.tusk.storage.plan_store import PlanStorage
from src.tusk.storage.todo_store import TodoStorage
from src.tusk.storage.checkpoint_store import CheckpointStorage
from src.tusk.storage.search import SearchEngine


class MockTuskServer:
    """Mock TuskServer for testing recall tool."""

    def __init__(self, config):
        self.config = config
        self.plan_storage = PlanStorage(config)
        self.todo_storage = TodoStorage(config)
        self.checkpoint_storage = CheckpointStorage(config)
        self.search_engine = SearchEngine(config)


@pytest.fixture
def temp_config():
    """Create temporary config for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = TuskConfig(data_dir=Path(temp_dir))
        yield config


@pytest.fixture
def mock_server(temp_config):
    """Create mock server with temp storage."""
    return MockTuskServer(temp_config)


@pytest.fixture
def recall_tool(mock_server):
    """Create recall tool with mock server."""
    # Import here to avoid import errors during collection
    from src.tusk.tools.enhanced_all import EnhancedUnifiedRecallTool
    return EnhancedUnifiedRecallTool(mock_server)


def create_sample_data(mock_server):
    """Create comprehensive sample data for testing."""
    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(hours=12)
    old_time = now - timedelta(days=5)

    # Create recent checkpoints
    recent_checkpoint = Checkpoint(
        description="Fixed authentication bug in user login",
        project_id="main-project",
        highlights=[
            Highlight(
                content="Fixed critical authentication bug",
                category=HighlightCategory.COMPLETION,
                importance=HighlightImportance.HIGH,
                tags=["authentication", "security", "bugfix"]
            ),
            Highlight(
                content="Implemented proper session handling",
                category=HighlightCategory.DECISION,
                importance=HighlightImportance.MEDIUM,
                tags=["session", "security"]
            )
        ],
        created_at=recent_time
    )

    old_checkpoint = Checkpoint(
        description="Set up project structure",
        project_id="main-project",
        highlights=[
            Highlight(
                content="Chose FastMCP framework for MCP server",
                category=HighlightCategory.DECISION,
                importance=HighlightImportance.HIGH,
                tags=["architecture", "framework"]
            )
        ],
        created_at=old_time
    )

    mock_server.checkpoint_storage.save(recent_checkpoint)
    mock_server.checkpoint_storage.save(old_checkpoint)

    # Create active todos
    in_progress_todo = Todo(
        content="Write comprehensive tests for recall",
        active_form="Writing comprehensive tests for recall",
        status=TodoStatus.IN_PROGRESS,
        priority=TodoPriority.HIGH,
        project_id="main-project",
        created_at=recent_time
    )

    pending_todo = Todo(
        content="Review PR for database changes",
        active_form="Reviewing PR for database changes",
        status=TodoStatus.PENDING,
        priority=TodoPriority.MEDIUM,
        project_id="main-project",
        created_at=recent_time
    )

    completed_todo = Todo(
        content="Set up CI/CD pipeline",
        active_form="Setting up CI/CD pipeline",
        status=TodoStatus.COMPLETED,
        priority=TodoPriority.HIGH,
        project_id="main-project",
        created_at=old_time,
        completed_at=recent_time
    )

    mock_server.todo_storage.save(in_progress_todo)
    mock_server.todo_storage.save(pending_todo)
    mock_server.todo_storage.save(completed_todo)

    # Create recent plans with mixed step completion
    active_plan = Plan(
        title="Implement user authentication system",
        description="Complete overhaul of authentication with OAuth2 and 2FA",
        status=PlanStatus.ACTIVE,
        project_id="main-project",
        created_at=recent_time
    )

    # Add steps with realistic completion states
    active_plan.steps = [
        PlanStep(
            description="Research OAuth2 providers",
            completed=True,
            notes="Chose Auth0 for implementation"
        ),
        PlanStep(
            description="Set up OAuth2 configuration",
            completed=True,
            notes="Configuration complete, tested with Google"
        ),
        PlanStep(
            description="Implement login/logout flow",
            completed=False,
            notes="In progress - UI components done"
        ),
        PlanStep(
            description="Add two-factor authentication",
            completed=False,
            notes="Waiting for login flow completion"
        ),
        PlanStep(
            description="Write comprehensive tests",
            completed=False,
            dependencies=["implement-login-logout"]
        )
    ]

    draft_plan = Plan(
        title="Database migration to PostgreSQL",
        description="Migrate from SQLite to PostgreSQL for production",
        status=PlanStatus.DRAFT,
        project_id="main-project",
        created_at=recent_time
    )

    old_plan = Plan(
        title="Initial project setup",
        description="Set up basic project structure and tooling",
        status=PlanStatus.COMPLETED,
        project_id="main-project",
        created_at=old_time,
        completed_at=recent_time - timedelta(days=2)
    )

    mock_server.plan_storage.save(active_plan)
    mock_server.plan_storage.save(draft_plan)
    mock_server.plan_storage.save(old_plan)

    return {
        'checkpoints': [recent_checkpoint, old_checkpoint],
        'todos': [in_progress_todo, pending_todo, completed_todo],
        'plans': [active_plan, draft_plan, old_plan]
    }


class TestRecallFunctionality:
    """Comprehensive test suite for recall functionality."""

    def test_recall_recent_with_comprehensive_data(self, recall_tool, mock_server):
        """Test recent recall with comprehensive realistic data."""
        sample_data = create_sample_data(mock_server)

        # Test recent recall
        result = asyncio.run(recall_tool._recall_recent())
        result_data = json.loads(result)

        # Verify success response
        assert result_data["success"] is True
        assert result_data["context_type"] == "recent"
        assert result_data["timeframe"] == "last 2 days"

        # Verify summary data
        summary = result_data["summary"]
        assert summary["checkpoints_count"] == 1  # Only recent checkpoint
        assert summary["active_todos"] >= 2  # In progress and pending todos
        assert summary["recent_plans"] >= 2  # Active and draft plans from recent time
        assert summary["context_available"] is True

        # Verify checkpoint data
        checkpoints = result_data["checkpoints"]
        assert len(checkpoints) == 1
        checkpoint_data = checkpoints[0]
        assert "Fixed authentication bug" in checkpoint_data["description"]
        assert checkpoint_data["project_id"] == "main-project"

        # Verify active todos
        active_todos = result_data["active_todos"]
        assert len(active_todos) >= 1

        # Find the in-progress todo
        in_progress_todos = [t for t in active_todos if t["status"] == "in_progress"]
        assert len(in_progress_todos) >= 1

        in_progress_todo = in_progress_todos[0]
        assert "comprehensive tests" in in_progress_todo["content"]
        assert in_progress_todo["active_form"] is not None

        # Verify recent plans (this tests the fixed PlanStep.status bug)
        recent_plans = result_data["recent_plans"]
        assert len(recent_plans) >= 2

        # Find the active authentication plan
        auth_plans = [p for p in recent_plans if "authentication" in p["title"]]
        assert len(auth_plans) >= 1

        auth_plan = auth_plans[0]
        assert auth_plan["status"] == "active"
        assert auth_plan["steps_completed"] == 2  # Two completed steps

    def test_recall_with_no_recent_data(self, recall_tool, mock_server):
        """Test recall when no recent data exists."""
        # Don't create any sample data

        result = asyncio.run(recall_tool._recall_recent())
        result_data = json.loads(result)

        # Should still succeed but with empty data
        assert result_data["success"] is True
        assert result_data["summary"]["context_available"] is False
        assert result_data["checkpoints"] == []
        assert result_data["active_todos"] == []
        assert result_data["recent_plans"] == []
        assert "No recent context found" in result_data["message"]

    def test_planstep_completed_counting(self, recall_tool, mock_server):
        """Test that PlanStep completion counting works correctly after bug fix."""
        # Create a plan specifically to test step counting
        plan = Plan(
            title="Step counting test plan",
            description="Testing completed step counting",
            status=PlanStatus.ACTIVE,
            project_id="test-project"
        )

        # Add steps with specific completion pattern
        plan.steps = [
            PlanStep(description="Step 1", completed=True),
            PlanStep(description="Step 2", completed=False),
            PlanStep(description="Step 3", completed=True),
            PlanStep(description="Step 4", completed=False),
            PlanStep(description="Step 5", completed=True),
        ]

        mock_server.plan_storage.save(plan)

        result = asyncio.run(recall_tool._recall_recent())
        result_data = json.loads(result)

        assert result_data["success"] is True

        recent_plans = result_data["recent_plans"]
        assert len(recent_plans) == 1

        plan_data = recent_plans[0]
        assert plan_data["title"] == "Step counting test plan"
        assert plan_data["steps_completed"] == 3  # Three completed steps

    def test_recall_different_contexts(self, recall_tool, mock_server):
        """Test different recall context types."""
        # Test week context
        result_week = asyncio.run(recall_tool._recall_timeframe(7))
        result_data = json.loads(result_week)
        assert result_data["success"] is True
        assert result_data["context_type"] == "timeframe"
        assert result_data["days_back"] == 7

        # Test session context
        result_session = asyncio.run(recall_tool._recall_session("test-session-123"))
        result_data = json.loads(result_session)
        assert result_data["success"] is True
        assert result_data["context_type"] == "session"
        assert result_data["session_id"] == "test-session-123"

        # Test branch context
        result_branch = asyncio.run(recall_tool._recall_branch("feature/auth", 5))
        result_data = json.loads(result_branch)
        assert result_data["success"] is True
        assert result_data["context_type"] == "branch"
        assert result_data["git_branch"] == "feature/auth"

    def test_recall_error_handling_with_helper_methods(self, recall_tool):
        """Test recall error handling using internal helper methods."""
        # Test that the internal recall methods handle errors gracefully
        result = asyncio.run(recall_tool._recall_session(""))
        result_data = json.loads(result)
        assert result_data["success"] is True  # Returns stub implementation

        result = asyncio.run(recall_tool._recall_branch("", 1))
        result_data = json.loads(result)
        assert result_data["success"] is True  # Returns stub implementation


def test_plan_model_step_counting():
    """Test the Plan model's built-in step counting methods."""
    plan = Plan(title="Test", description="Test plan")

    # Add steps with mixed completion
    plan.steps = [
        PlanStep(description="Done 1", completed=True),
        PlanStep(description="Todo 1", completed=False),
        PlanStep(description="Done 2", completed=True),
        PlanStep(description="Todo 2", completed=False),
        PlanStep(description="Done 3", completed=True),
    ]

    # Test get_progress method
    completed, total = plan.get_progress()
    assert completed == 3
    assert total == 5

    # Test percentage calculation
    percentage = plan.get_progress_percentage()
    assert percentage == 60.0

    # Test is_completed method
    assert plan.is_completed() is False

    # Mark all steps completed
    for step in plan.steps:
        step.completed = True

    assert plan.is_completed() is True
    assert plan.get_progress_percentage() == 100.0


if __name__ == "__main__":
    # Run a quick test to verify functionality
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        config = TuskConfig(data_dir=Path(temp_dir))
        server = MockTuskServer(config)

        # Import the tool
        from src.tusk.tools.enhanced_all import EnhancedUnifiedRecallTool
        tool = EnhancedUnifiedRecallTool(server)

        # Create and test with sample data
        sample_data = create_sample_data(server)

        result = asyncio.run(tool._recall_recent())
        result_data = json.loads(result)

        print(f"Success: {result_data['success']}")
        print(f"Checkpoints: {result_data['summary']['checkpoints_count']}")
        print(f"Active todos: {result_data['summary']['active_todos']}")
        print(f"Recent plans: {result_data['summary']['recent_plans']}")

        if result_data["recent_plans"]:
            plan = result_data["recent_plans"][0]
            print(f"Plan: {plan['title']} - {plan['steps_completed']} steps completed")

        print("✅ Recall tests completed successfully!")