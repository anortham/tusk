"""Comprehensive tests for plan functionality.

Tests the plan tool end-to-end with realistic data to ensure
all plan operations work correctly.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models.plan import Plan, PlanStep, PlanStatus
from src.tusk.storage.plan_store import PlanStorage


class MockTuskServer:
    """Mock TuskServer for testing plan tool."""

    def __init__(self, config):
        self.config = config
        self.plan_storage = PlanStorage(config)
        # Add other required storages as mocks
        self.checkpoint_storage = Mock()
        self.todo_storage = Mock()
        self.search_engine = Mock()


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
def plan_tool(mock_server):
    """Create plan tool with mock server."""
    from src.tusk.tools.enhanced_all import EnhancedUnifiedPlanTool
    return EnhancedUnifiedPlanTool(mock_server)


def create_sample_plan(mock_server):
    """Create a sample plan for testing."""
    plan = Plan(
        title="Implement user authentication system",
        description="Complete overhaul of authentication with OAuth2 and 2FA",
        status=PlanStatus.ACTIVE,
        project_id="auth-project",
        goals=["Secure user authentication", "OAuth2 integration", "Two-factor auth"],
        success_criteria=["All tests pass", "Security audit complete", "Production ready"]
    )

    # Add steps with dependencies
    plan.steps = [
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
            notes="In progress - UI components done",
            estimated_duration="2d"
        ),
        PlanStep(
            description="Add two-factor authentication",
            completed=False,
            dependencies=["step-login-logout"],  # Simplified dependency
            estimated_duration="1d"
        ),
        PlanStep(
            description="Write comprehensive tests",
            completed=False,
            dependencies=["step-login-logout", "step-2fa"],
            estimated_duration="1d"
        )
    ]

    mock_server.plan_storage.save(plan)
    return plan


class TestPlanFunctionality:
    """Comprehensive test suite for plan functionality."""

    def test_plan_creation(self, plan_tool, mock_server):
        """Test creating a new plan."""
        # Create a new plan
        result = asyncio.run(plan_tool._create_plan(
            title="Database migration to PostgreSQL",
            description="Migrate from SQLite to PostgreSQL for production scalability"
        ))

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert "plan_id" in result_data

        plan_id = result_data["plan_id"]
        assert plan_id is not None

        # Verify the plan was saved
        plan = mock_server.plan_storage.load(plan_id)
        assert plan is not None
        assert plan.title == "Database migration to PostgreSQL"
        assert plan.status == PlanStatus.DRAFT
        assert len(plan.steps) == 0  # New plan starts with no steps

    def test_plan_listing(self, plan_tool, mock_server):
        """Test listing plans."""
        # Create multiple plans
        plan1 = create_sample_plan(mock_server)

        plan2 = Plan(
            title="Database migration",
            description="Migrate to PostgreSQL",
            status=PlanStatus.DRAFT
        )
        mock_server.plan_storage.save(plan2)

        plan3 = Plan(
            title="Completed project",
            description="Already done",
            status=PlanStatus.COMPLETED
        )
        mock_server.plan_storage.save(plan3)

        # Test listing all plans
        result = asyncio.run(plan_tool._list_plans(limit=10))
        result_data = json.loads(result)

        assert result_data["success"] is True
        assert "plans" in result_data

        plans = result_data["plans"]
        assert len(plans) == 3

        # Verify plan data structure
        for plan_data in plans:
            assert "id" in plan_data
            assert "title" in plan_data
            assert "status" in plan_data
            assert "progress" in plan_data
            assert "total_steps" in plan_data
            assert "completed_steps" in plan_data

        # Find the auth plan and verify step counting
        auth_plans = [p for p in plans if "authentication" in p["title"]]
        assert len(auth_plans) == 1

        auth_plan = auth_plans[0]
        assert auth_plan["total_steps"] == 5
        assert auth_plan["completed_steps"] == 2  # Two completed steps
        assert auth_plan["progress"] == 40.0  # 2/5 * 100

    def test_plan_activation(self, plan_tool, mock_server):
        """Test activating a plan."""
        # Create a draft plan
        plan = Plan(
            title="Test activation",
            description="Test plan activation",
            status=PlanStatus.DRAFT
        )
        mock_server.plan_storage.save(plan)

        # Activate the plan
        result = asyncio.run(plan_tool._activate_plan(plan.id))
        result_data = json.loads(result)

        assert result_data["success"] is True

        # Verify the plan is now active
        updated_plan = mock_server.plan_storage.load(plan.id)
        assert updated_plan.status == PlanStatus.ACTIVE
        assert updated_plan.started_at is not None

    def test_plan_completion(self, plan_tool, mock_server):
        """Test completing a plan."""
        plan = create_sample_plan(mock_server)

        # Complete the plan
        result = asyncio.run(plan_tool._complete_plan(plan.id))
        result_data = json.loads(result)

        assert result_data["success"] is True

        # Verify the plan is now completed
        updated_plan = mock_server.plan_storage.load(plan.id)
        assert updated_plan.status == PlanStatus.COMPLETED
        assert updated_plan.completed_at is not None

    def test_add_step_to_plan(self, plan_tool, mock_server):
        """Test adding a step to a plan."""
        plan = create_sample_plan(mock_server)
        initial_step_count = len(plan.steps)

        # Add a new step
        result = asyncio.run(plan_tool._add_step(
            plan_id=plan.id,
            step_description="Perform security audit",
            estimated_duration="3d",
            dependencies=[]
        ))

        result_data = json.loads(result)
        assert result_data["success"] is True

        # Verify the step was added
        updated_plan = mock_server.plan_storage.load(plan.id)
        assert len(updated_plan.steps) == initial_step_count + 1

        # Find the new step
        new_steps = [s for s in updated_plan.steps if "security audit" in s.description]
        assert len(new_steps) == 1

        new_step = new_steps[0]
        assert new_step.estimated_duration == "3d"
        assert new_step.completed is False

    def test_complete_step(self, plan_tool, mock_server):
        """Test completing a step in a plan."""
        plan = create_sample_plan(mock_server)

        # Find an incomplete step
        incomplete_steps = [s for s in plan.steps if not s.completed]
        assert len(incomplete_steps) > 0

        step_to_complete = incomplete_steps[0]
        step_id = step_to_complete.id

        # Complete the step
        result = asyncio.run(plan_tool._complete_step(plan.id, step_id))
        result_data = json.loads(result)

        assert result_data["success"] is True

        # Verify the step is completed
        updated_plan = mock_server.plan_storage.load(plan.id)
        completed_step = next((s for s in updated_plan.steps if s.id == step_id), None)
        assert completed_step is not None
        assert completed_step.completed is True
        assert completed_step.completed_at is not None

    def test_plan_search(self, plan_tool, mock_server):
        """Test searching for plans."""
        # Create plans with searchable content
        plan1 = Plan(
            title="User authentication system",
            description="OAuth2 and JWT tokens for secure login",
            goals=["Security", "OAuth2", "JWT"]
        )
        mock_server.plan_storage.save(plan1)

        plan2 = Plan(
            title="Database optimization",
            description="Improve PostgreSQL performance and indexing",
            goals=["Performance", "Database", "PostgreSQL"]
        )
        mock_server.plan_storage.save(plan2)

        plan3 = Plan(
            title="API documentation",
            description="Create comprehensive REST API documentation",
            goals=["Documentation", "API", "REST"]
        )
        mock_server.plan_storage.save(plan3)

        # Search for authentication-related plans
        result = asyncio.run(plan_tool._search_plans("authentication OAuth2"))
        result_data = json.loads(result)

        assert result_data["success"] is True
        assert "plans" in result_data

        plans = result_data["plans"]
        assert len(plans) >= 1

        # Should find the authentication plan
        auth_plans = [p for p in plans if "authentication" in p["title"]]
        assert len(auth_plans) >= 1

        # Search for database-related plans
        result = asyncio.run(plan_tool._search_plans("database PostgreSQL"))
        result_data = json.loads(result)

        plans = result_data["plans"]
        db_plans = [p for p in plans if "Database" in p["title"] or "database" in p["description"]]
        assert len(db_plans) >= 1

    def test_plan_with_no_steps_progress(self, plan_tool, mock_server):
        """Test plan progress calculation with no steps."""
        plan = Plan(
            title="Empty plan",
            description="Plan with no steps"
        )
        mock_server.plan_storage.save(plan)

        result = asyncio.run(plan_tool._list_plans(limit=1))
        result_data = json.loads(result)

        plans = result_data["plans"]
        empty_plan = next((p for p in plans if p["title"] == "Empty plan"), None)
        assert empty_plan is not None
        assert empty_plan["total_steps"] == 0
        assert empty_plan["completed_steps"] == 0
        assert empty_plan["progress"] == 0.0

    def test_plan_error_handling(self, plan_tool, mock_server):
        """Test error handling for invalid operations."""
        # Test completing non-existent plan
        result = asyncio.run(plan_tool._complete_plan("non-existent-id"))
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "not found" in result_data["error"].lower()

        # Test completing non-existent step
        plan = create_sample_plan(mock_server)
        result = asyncio.run(plan_tool._complete_step(plan.id, "non-existent-step"))
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "step not found" in result_data["error"].lower()


def test_plan_model_step_management():
    """Test the Plan model's step management methods directly."""
    plan = Plan(title="Test Plan", description="Testing step management")

    # Test adding steps
    step1 = plan.add_step("First step", estimated_duration="1h")
    assert len(plan.steps) == 1
    assert step1.description == "First step"
    assert step1.estimated_duration == "1h"

    step2 = plan.add_step("Second step", notes="Important step")
    assert len(plan.steps) == 2
    assert step2.notes == "Important step"

    # Test completing steps
    success = plan.complete_step(step1.id)
    assert success is True
    assert step1.completed is True
    assert step1.completed_at is not None

    # Test progress calculation
    completed, total = plan.get_progress()
    assert completed == 1
    assert total == 2
    assert plan.get_progress_percentage() == 50.0

    # Test next steps
    next_steps = plan.get_next_steps()
    assert len(next_steps) == 1
    assert next_steps[0] == step2

    # Complete all steps
    plan.complete_step(step2.id)
    assert plan.is_completed() is True

    # Test that completed plan has no next steps
    next_steps = plan.get_next_steps()
    assert len(next_steps) == 0


def test_plan_dependencies():
    """Test plan step dependencies."""
    plan = Plan(title="Dependency Test", description="Testing step dependencies")

    # Add steps with dependencies
    step1 = plan.add_step("Foundation step")
    step2 = plan.add_step("Dependent step", dependencies=[step1.id])
    step3 = plan.add_step("Final step", dependencies=[step1.id, step2.id])

    # Initially, only foundation step should be actionable
    next_steps = plan.get_next_steps()
    assert len(next_steps) == 1
    assert next_steps[0] == step1

    # Complete foundation step
    plan.complete_step(step1.id)

    # Now dependent step should be actionable
    next_steps = plan.get_next_steps()
    assert len(next_steps) == 1
    assert next_steps[0] == step2

    # Complete dependent step
    plan.complete_step(step2.id)

    # Now final step should be actionable
    next_steps = plan.get_next_steps()
    assert len(next_steps) == 1
    assert next_steps[0] == step3


if __name__ == "__main__":
    # Run a quick test to verify functionality
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        config = TuskConfig(data_dir=Path(temp_dir))
        server = MockTuskServer(config)

        from src.tusk.tools.enhanced_all import EnhancedUnifiedPlanTool
        tool = EnhancedUnifiedPlanTool(server)

        # Test creating a plan
        result = asyncio.run(tool._create_plan(
            "Test Plan",
            "Testing plan creation"
        ))
        result_data = json.loads(result)
        print(f"Plan creation success: {result_data['success']}")

        # Test plan model methods
        plan = Plan(title="Direct Test", description="Testing model")
        step = plan.add_step("Test step")
        plan.complete_step(step.id)

        progress = plan.get_progress_percentage()
        print(f"Plan progress: {progress}% (should be 100.0)")

        print("Plan tests completed successfully!")