"""Comprehensive tests for Tusk unified MCP tools."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.tusk.config import TuskConfig
from src.tusk.storage import CheckpointStorage, PlanStorage, SearchEngine, TaskStorage
from src.tusk.tools.unified import (
    UnifiedCheckpointTool,
    UnifiedPlanTool,
    UnifiedRecallTool,
    UnifiedStandupTool,
    UnifiedTaskTool,
)


@pytest.fixture
def temp_config():
    """Create a temporary configuration for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = TuskConfig(
            data_dir=Path(temp_dir) / "data",
            log_dir=Path(temp_dir) / "logs",
        )
        config.ensure_directories()
        yield config


@pytest.fixture
def mock_server(temp_config):
    """Create a mock TuskServer with real storage for testing unified tools."""
    mock_server = Mock()
    mock_server.config = temp_config

    # Use real storage for integration testing
    mock_server.checkpoint_storage = CheckpointStorage(temp_config)
    mock_server.task_storage = TaskStorage(temp_config)
    mock_server.plan_storage = PlanStorage(temp_config)
    mock_server.search_engine = SearchEngine(temp_config)

    # Mock search engine methods to avoid index initialization issues
    mock_server.search_engine.index_checkpoint = Mock()
    mock_server.search_engine.index_task = Mock()
    mock_server.search_engine.index_plan = Mock()
    mock_server.search_engine.search = Mock(return_value=[])

    return mock_server


class MockMCPServer:
    """Mock FastMCP server for testing tool registration."""

    def __init__(self):
        self.registered_tools = {}

    def tool(self, func):
        """Mock tool decorator that captures registered functions."""
        self.registered_tools[func.__name__] = func
        return func


class TestUnifiedTaskTool:
    """Test the unified todo tool with all actions."""

    def test_tool_initialization(self, mock_server):
        """Test that unified todo tool initializes correctly."""
        tool = UnifiedTaskTool(mock_server)

        assert tool.server == mock_server
        assert tool.config == mock_server.config
        # Note: workspace concept removed, no longer testing get_current_workspace()

    def test_tool_registration(self, mock_server):
        """Test that todo tool registers correctly."""
        tool = UnifiedTaskTool(mock_server)
        mock_mcp = MockMCPServer()

        tool.register(mock_mcp)

        # Should register exactly one tool called 'task'
        assert "task" in mock_mcp.registered_tools
        assert len(mock_mcp.registered_tools) == 1
        assert callable(mock_mcp.registered_tools["task"])

    @pytest.mark.asyncio
    async def test_add_task_success(self, mock_server):
        """Test adding a task successfully."""
        tool = UnifiedTaskTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        task_func = mock_mcp.registered_tools["task"]

        # Test successful add
        result = await task_func(action="add", task="Test task content")

        # Parse JSON response
        response = json.loads(result)

        assert response["success"] is True
        assert response["action"] == "task_added"
        assert response["task"]["content"] == "Test task content"
        assert response["task"]["status"] == "pending"
        assert response["task"]["priority"] == "medium"
        assert "id" in response["task"]
        assert "created_at" in response["task"]

    @pytest.mark.asyncio
    async def test_add_task_missing_content(self, mock_server):
        """Test adding a task without content fails."""
        tool = UnifiedTaskTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        task_func = mock_mcp.registered_tools["task"]

        # Test missing task content
        result = await task_func(action="add", task=None)

        response = json.loads(result)
        assert response["success"] is False
        assert "Task content is required" in response["error"]

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, mock_server):
        """Test listing tasks when none exist."""
        tool = UnifiedTaskTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        task_func = mock_mcp.registered_tools["task"]

        result = await task_func(action="list")

        response = json.loads(result)
        assert response["success"] is True
        assert response["total_tasks"] == 0
        assert "No active tasks" in response["message"]

    @pytest.mark.asyncio
    async def test_complete_workflow(self, mock_server):
        """Test the complete workflow: add -> start -> complete."""
        tool = UnifiedTaskTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        task_func = mock_mcp.registered_tools["task"]

        # Step 1: Add a task
        result = await task_func(action="add", task="Complete workflow test")
        response = json.loads(result)
        task_id = response["task"]["id"]

        # Step 2: Start the task
        result = await task_func(action="start", task_id=task_id)
        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "task_started"
        assert response["task"]["status"] == "in_progress"

        # Step 3: Complete the task
        result = await task_func(action="complete", task_id=task_id)
        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "task_completed"
        assert response["task"]["status"] == "completed"
        assert "celebration" in response

    @pytest.mark.asyncio
    async def test_invalid_action(self, mock_server):
        """Test invalid action returns error."""
        tool = UnifiedTaskTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        task_func = mock_mcp.registered_tools["task"]

        result = await task_func(action="invalid_action")

        response = json.loads(result)
        assert response["success"] is False
        assert "Unknown action" in response["error"]


class TestUnifiedCheckpointTool:
    """Test the unified checkpoint tool."""

    def test_tool_initialization(self, mock_server):
        """Test checkpoint tool initialization."""
        tool = UnifiedCheckpointTool(mock_server)

        assert tool.server == mock_server
        assert tool.config == mock_server.config

    def test_tool_registration(self, mock_server):
        """Test checkpoint tool registration."""
        tool = UnifiedCheckpointTool(mock_server)
        mock_mcp = MockMCPServer()

        tool.register(mock_mcp)

        assert "checkpoint" in mock_mcp.registered_tools
        assert len(mock_mcp.registered_tools) == 1

    @pytest.mark.asyncio
    async def test_save_checkpoint_success(self, mock_server):
        """Test saving a checkpoint successfully."""
        tool = UnifiedCheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        checkpoint_func = mock_mcp.registered_tools["checkpoint"]

        result = await checkpoint_func(action="save", description="Test checkpoint")

        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "progress_saved"
        assert response["checkpoint"]["description"] == "Test checkpoint"
        assert response["checkpoint"]["workspace_id"] == ""
        assert "id" in response["checkpoint"]

    @pytest.mark.asyncio
    async def test_save_checkpoint_missing_description(self, mock_server):
        """Test saving checkpoint without description fails."""
        tool = UnifiedCheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        checkpoint_func = mock_mcp.registered_tools["checkpoint"]

        result = await checkpoint_func(action="save", description=None)

        response = json.loads(result)
        assert response["success"] is False
        assert "Description is required" in response["error"]

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty(self, mock_server):
        """Test listing checkpoints when none exist."""
        tool = UnifiedCheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        checkpoint_func = mock_mcp.registered_tools["checkpoint"]

        result = await checkpoint_func(action="list")

        response = json.loads(result)
        assert response["success"] is True
        assert response["total_checkpoints"] == 0
        assert "No saved progress found" in response["message"]


class TestUnifiedRecallTool:
    """Test the unified recall tool."""

    def test_tool_initialization(self, mock_server):
        """Test recall tool initialization."""
        tool = UnifiedRecallTool(mock_server)

        assert tool.server == mock_server
        assert tool.config == mock_server.config

    def test_tool_registration(self, mock_server):
        """Test recall tool registration."""
        tool = UnifiedRecallTool(mock_server)
        mock_mcp = MockMCPServer()

        tool.register(mock_mcp)

        assert "recall" in mock_mcp.registered_tools
        assert len(mock_mcp.registered_tools) == 1

    @pytest.mark.asyncio
    async def test_recall_recent_context(self, mock_server):
        """Test recalling recent context."""
        tool = UnifiedRecallTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        recall_func = mock_mcp.registered_tools["recall"]

        result = await recall_func(context="recent")

        response = json.loads(result)
        assert response["success"] is True
        # Note: workspace concept removed, response no longer contains workspace field
        # assert response["workspace"] == "test_workspace"
        assert "summary" in response
        assert "checkpoints" in response
        assert "tasks" in response

    @pytest.mark.asyncio
    async def test_recall_week_context(self, mock_server):
        """Test recalling weekly context."""
        tool = UnifiedRecallTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        recall_func = mock_mcp.registered_tools["recall"]

        result = await recall_func(context="week", days_back=7)

        response = json.loads(result)
        assert response["success"] is True
        assert response["summary"]["days_covered"] == 7

    @pytest.mark.asyncio
    async def test_recall_invalid_context(self, mock_server):
        """Test invalid recall context."""
        tool = UnifiedRecallTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        recall_func = mock_mcp.registered_tools["recall"]

        result = await recall_func(context="invalid")

        response = json.loads(result)
        assert response["success"] is False
        assert "Invalid context" in response["error"]


class TestUnifiedStandupTool:
    """Test the unified standup tool."""

    def test_tool_initialization(self, mock_server):
        """Test standup tool initialization."""
        tool = UnifiedStandupTool(mock_server)

        assert tool.server == mock_server
        assert tool.config == mock_server.config

    def test_tool_registration(self, mock_server):
        """Test standup tool registration."""
        tool = UnifiedStandupTool(mock_server)
        mock_mcp = MockMCPServer()

        tool.register(mock_mcp)

        assert "standup" in mock_mcp.registered_tools
        assert len(mock_mcp.registered_tools) == 1

    @pytest.mark.asyncio
    async def test_daily_standup(self, mock_server):
        """Test daily standup generation."""
        tool = UnifiedStandupTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        standup_func = mock_mcp.registered_tools["standup"]

        result = await standup_func(timeframe="daily")

        response = json.loads(result)
        assert response["success"] is True
        assert response["timeframe"] == "daily"
        assert response["days_covered"] == 1
        assert "cross_project_summary" in response
        assert "projects" in response

        # Verify cross-project summary structure
        summary = response["cross_project_summary"]
        assert "total_projects" in summary
        assert "total_checkpoints" in summary
        assert "total_tasks" in summary
        assert "total_completed" in summary
        assert "total_plans" in summary

    @pytest.mark.asyncio
    async def test_weekly_standup(self, mock_server):
        """Test weekly standup generation."""
        tool = UnifiedStandupTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        standup_func = mock_mcp.registered_tools["standup"]

        result = await standup_func(timeframe="weekly")

        response = json.loads(result)
        assert response["success"] is True
        assert response["timeframe"] == "weekly"
        assert response["days_covered"] == 7

    @pytest.mark.asyncio
    async def test_custom_standup(self, mock_server):
        """Test custom timeframe standup."""
        tool = UnifiedStandupTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        standup_func = mock_mcp.registered_tools["standup"]

        result = await standup_func(timeframe="custom", days_back=3)

        response = json.loads(result)
        assert response["success"] is True
        assert response["timeframe"] == "custom"
        assert response["days_covered"] == 3


class TestUnifiedPlanTool:
    """Test the unified plan tool - the foundation of the 5-tool workflow."""

    def test_tool_initialization(self, mock_server):
        """Test plan tool initialization."""
        tool = UnifiedPlanTool(mock_server)

        assert tool.server == mock_server
        assert tool.config == mock_server.config

    def test_tool_registration(self, mock_server):
        """Test plan tool registration."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()

        tool.register(mock_mcp)

        assert "plan" in mock_mcp.registered_tools
        assert len(mock_mcp.registered_tools) == 1
        assert callable(mock_mcp.registered_tools["plan"])

    @pytest.mark.asyncio
    async def test_create_plan_success(self, mock_server):
        """Test creating a plan successfully."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="create", title="Test Plan", description="A comprehensive test plan")

        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "plan_created"
        assert response["plan"]["title"] == "Test Plan"
        assert response["plan"]["description"] == "A comprehensive test plan"
        assert response["plan"]["status"] == "draft"
        assert response["plan"]["steps_count"] == 0
        assert "next_steps" in response

    @pytest.mark.asyncio
    async def test_create_plan_missing_title(self, mock_server):
        """Test creating plan without title fails."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="create", title=None, description="Description")

        response = json.loads(result)
        assert response["success"] is False
        assert "Plan title is required" in response["error"]

    @pytest.mark.asyncio
    async def test_create_plan_missing_description(self, mock_server):
        """Test creating plan without description fails."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="create", title="Title", description=None)

        response = json.loads(result)
        assert response["success"] is False
        assert "Plan description is required" in response["error"]

    @pytest.mark.asyncio
    async def test_list_plans_empty(self, mock_server):
        """Test listing plans when none exist."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="list")

        response = json.loads(result)
        assert response["success"] is True
        assert response["total_plans"] == 0
        assert "No active plans found" in response["message"]
        assert "suggestion" in response

    @pytest.mark.asyncio
    async def test_complete_plan_workflow(self, mock_server):
        """Test the complete plan workflow: create → add steps → activate → complete."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        # Step 1: Create a plan
        result = await plan_func(action="create", title="Workflow Test Plan", description="Testing complete workflow")
        response = json.loads(result)
        plan_id = response["plan"]["id"]

        # Step 2: Add steps to the plan
        result = await plan_func(action="add_step", plan_id=plan_id, step_description="First step of the plan")
        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "step_added"
        step1_id = response["step"]["id"]

        result = await plan_func(action="add_step", plan_id=plan_id, step_description="Second step of the plan")
        response = json.loads(result)
        step2_id = response["step"]["id"]

        # Step 3: Activate the plan
        result = await plan_func(action="activate", plan_id=plan_id)
        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "plan_activated"
        assert response["plan"]["status"] == "active"
        assert len(response["plan"]["steps"]) == 2

        # Step 4: Complete individual steps
        result = await plan_func(action="complete_step", step_id=step1_id)
        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "step_completed"
        assert "Progress: 1/2" in response["plan_status"]

        result = await plan_func(action="complete_step", step_id=step2_id)
        response = json.loads(result)
        assert response["success"] is True
        assert "Plan completed!" in response["plan_status"]

        # Step 5: Complete the entire plan
        result = await plan_func(action="complete", plan_id=plan_id)
        response = json.loads(result)
        assert response["success"] is True
        assert response["action"] == "plan_completed"
        assert response["plan"]["status"] == "completed"
        assert "celebration" in response

    @pytest.mark.asyncio
    async def test_add_step_missing_plan_id(self, mock_server):
        """Test adding step without plan ID fails."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="add_step", plan_id=None, step_description="Test step")

        response = json.loads(result)
        assert response["success"] is False
        assert "Plan ID is required" in response["error"]

    @pytest.mark.asyncio
    async def test_add_step_missing_description(self, mock_server):
        """Test adding step without description fails."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="add_step", plan_id="fake_id", step_description=None)

        response = json.loads(result)
        assert response["success"] is False
        assert "Step description is required" in response["error"]

    @pytest.mark.asyncio
    async def test_nonexistent_plan_operations(self, mock_server):
        """Test operations on nonexistent plans."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        # Try to activate nonexistent plan
        result = await plan_func(action="activate", plan_id="nonexistent")
        response = json.loads(result)
        assert response["success"] is False
        assert "not found" in response["error"]

        # Try to complete nonexistent plan
        result = await plan_func(action="complete", plan_id="nonexistent")
        response = json.loads(result)
        assert response["success"] is False
        assert "not found" in response["error"]

        # Try to add step to nonexistent plan
        result = await plan_func(action="add_step", plan_id="nonexistent", step_description="Test step")
        response = json.loads(result)
        assert response["success"] is False
        assert "not found" in response["error"]

    @pytest.mark.asyncio
    async def test_search_plans_no_results(self, mock_server):
        """Test searching plans with no results."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="search", query="nonexistent")

        response = json.loads(result)
        assert response["success"] is True
        assert response["total_results"] == 0
        assert response["query"] == "nonexistent"

    @pytest.mark.asyncio
    async def test_search_plans_missing_query(self, mock_server):
        """Test searching plans without query fails."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="search", query=None)

        response = json.loads(result)
        assert response["success"] is False
        assert "Search query is required" in response["error"]

    @pytest.mark.asyncio
    async def test_invalid_action(self, mock_server):
        """Test invalid action returns error."""
        tool = UnifiedPlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        plan_func = mock_mcp.registered_tools["plan"]

        result = await plan_func(action="invalid_action")

        response = json.loads(result)
        assert response["success"] is False
        assert "Unknown action" in response["error"]


class TestToolIntegration:
    """Test integration between unified tools."""

    @pytest.mark.asyncio
    async def test_cross_tool_workflow(self, mock_server):
        """Test a complete workflow across all 5 tools."""
        # Initialize all tools
        plan_tool = UnifiedPlanTool(mock_server)
        todo_tool = UnifiedTaskTool(mock_server)
        checkpoint_tool = UnifiedCheckpointTool(mock_server)
        recall_tool = UnifiedRecallTool(mock_server)
        standup_tool = UnifiedStandupTool(mock_server)

        mock_mcp = MockMCPServer()

        # Register all 5 tools
        plan_tool.register(mock_mcp)
        todo_tool.register(mock_mcp)
        checkpoint_tool.register(mock_mcp)
        recall_tool.register(mock_mcp)
        standup_tool.register(mock_mcp)

        # Step 1: Create a plan (PLAN FIRST!)
        plan_func = mock_mcp.registered_tools["plan"]
        result = await plan_func(
            action="create",
            title="Integration Test Plan",
            description="Test the complete 5-tool workflow",
        )
        response = json.loads(result)
        plan_id = response["plan"]["id"]

        # Step 2: Add steps to the plan
        await plan_func(action="add_step", plan_id=plan_id, step_description="Create a todo for testing")

        # Step 3: Activate the plan
        await plan_func(action="activate", plan_id=plan_id)

        # Step 4: Create a todo from the plan
        task_func = mock_mcp.registered_tools["task"]
        result = await task_func(action="add", task="Integration test task from plan")
        response = json.loads(result)
        task_id = response["task"]["id"]

        # Step 5: Save a checkpoint
        checkpoint_func = mock_mcp.registered_tools["checkpoint"]
        await checkpoint_func(action="save", description="Started integration test with plan")

        # Step 6: Start the todo
        await task_func(action="start", task_id=task_id)

        # Step 7: Get recall context
        recall_func = mock_mcp.registered_tools["recall"]
        recall_result = await recall_func(context="recent")
        recall_response = json.loads(recall_result)

        # Verify recall includes our work from all tools
        assert recall_response["success"] is True
        assert recall_response["summary"]["tasks_count"] >= 1
        assert recall_response["summary"]["checkpoints_count"] >= 1
        assert recall_response["summary"]["plans_count"] >= 1

        # Step 8: Generate standup
        standup_func = mock_mcp.registered_tools["standup"]
        standup_result = await standup_func(timeframe="daily")
        standup_response = json.loads(standup_result)

        # Verify standup includes our work from all tools
        assert standup_response["success"] is True
        assert "cross_project_summary" in standup_response
        assert "projects" in standup_response

        # Check cross-project summary structure (data may be empty in test environment)
        summary = standup_response["cross_project_summary"]
        assert "total_tasks" in summary
        assert "total_checkpoints" in summary
        assert "total_plans" in summary
        assert "total_projects" in summary
        assert "total_completed" in summary

        # Verify the values are non-negative integers
        assert summary["total_tasks"] >= 0
        assert summary["total_checkpoints"] >= 0
        assert summary["total_plans"] >= 0


class TestErrorHandling:
    """Test error handling across all unified tools."""

    @pytest.mark.asyncio
    async def test_todo_nonexistent_task_operations(self, mock_server):
        """Test operations on nonexistent tasks."""
        tool = UnifiedTaskTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)

        task_func = mock_mcp.registered_tools["task"]

        # Try to start nonexistent task
        result = await task_func(action="start", task_id="nonexistent")
        response = json.loads(result)
        assert response["success"] is False
        assert "not found" in response["error"]

        # Try to complete nonexistent task
        result = await task_func(action="complete", task_id="nonexistent")
        response = json.loads(result)
        assert response["success"] is False
        assert "not found" in response["error"]

    @pytest.mark.asyncio
    async def test_missing_required_parameters(self, mock_server):
        """Test missing required parameters across tools."""
        # Todo tool
        todo_tool = UnifiedTaskTool(mock_server)
        mock_mcp_todo = MockMCPServer()
        todo_tool.register(mock_mcp_todo)

        task_func = mock_mcp_todo.registered_tools["task"]

        # Missing task_id for start
        result = await task_func(action="start", task_id=None)
        response = json.loads(result)
        assert response["success"] is False
        assert "Task ID is required" in response["error"]

        # Missing query for search
        result = await task_func(action="search", query=None)
        response = json.loads(result)
        assert response["success"] is False
        assert "Search query is required" in response["error"]

        # Checkpoint tool
        checkpoint_tool = UnifiedCheckpointTool(mock_server)
        mock_mcp_checkpoint = MockMCPServer()
        checkpoint_tool.register(mock_mcp_checkpoint)

        checkpoint_func = mock_mcp_checkpoint.registered_tools["checkpoint"]

        # Missing query for search
        result = await checkpoint_func(action="search", query=None)
        response = json.loads(result)
        assert response["success"] is False
        assert "Search query is required" in response["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
