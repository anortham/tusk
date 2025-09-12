"""Tests for Tusk MCP tools integration."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models import Checkpoint, Todo, Plan
from src.tusk.models.todo import TodoStatus, TodoPriority
from src.tusk.models.plan import PlanStatus
from src.tusk.storage import CheckpointStorage, TodoStorage, PlanStorage
from src.tusk.tools.checkpoint import CheckpointTool
from src.tusk.tools.todo import TodoTool
from src.tusk.tools.plan import PlanTool


@pytest.fixture
def temp_config():
    """Create a temporary configuration for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = TuskConfig(
            data_dir=Path(temp_dir) / "data",
            log_dir=Path(temp_dir) / "logs",
            current_workspace="test_workspace",
        )
        config.ensure_directories()
        yield config


@pytest.fixture
def mock_server(temp_config):
    """Create a mock TuskServer with real storage for testing tools."""
    mock_server = Mock()
    mock_server.config = temp_config
    
    # Use real storage for integration testing
    mock_server.checkpoint_storage = CheckpointStorage(temp_config)
    mock_server.todo_storage = TodoStorage(temp_config)
    mock_server.plan_storage = PlanStorage(temp_config)
    
    # Mock search engine
    mock_server.search_engine = Mock()
    mock_server.search_engine.index_checkpoint = Mock()
    mock_server.search_engine.index_todo = Mock()
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


class TestCheckpointToolIntegration:
    """Test checkpoint tool with real storage integration."""
    
    def test_tool_initialization(self, mock_server):
        """Test that checkpoint tool initializes correctly."""
        tool = CheckpointTool(mock_server)
        
        assert tool.server == mock_server
        assert tool.config == mock_server.config
        assert tool.get_current_workspace() == "test_workspace"
    
    def test_tool_registration(self, mock_server):
        """Test that tools register correctly with MCP server."""
        tool = CheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        
        tool.register(mock_mcp)
        
        # Verify expected tools were registered
        expected_tools = ['save_progress', 'list_recent_saves', 'search_checkpoints']
        for tool_name in expected_tools:
            assert tool_name in mock_mcp.registered_tools
            assert callable(mock_mcp.registered_tools[tool_name])
    
    @pytest.mark.asyncio
    async def test_save_progress_end_to_end(self, mock_server):
        """Test save_progress function end-to-end with real storage."""
        tool = CheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        save_progress = mock_mcp.registered_tools['save_progress']
        
        # Test successful save
        result = await save_progress("Test progress checkpoint")
        
        # Verify response
        assert "✅ Saved progress: Test progress checkpoint" in result
        assert "Checkpoint ID:" in result
        
        # Verify checkpoint was actually saved
        checkpoints = mock_server.checkpoint_storage.list_recent(limit=5)
        assert len(checkpoints) == 1
        assert checkpoints[0].description == "Test progress checkpoint"
        assert checkpoints[0].workspace_id == "test_workspace"
        
        # Verify search engine was called to index
        mock_server.search_engine.index_checkpoint.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_recent_saves(self, mock_server):
        """Test list_recent_saves function."""
        tool = CheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        # First save some checkpoints
        save_progress = mock_mcp.registered_tools['save_progress']
        await save_progress("First checkpoint")
        await save_progress("Second checkpoint")
        
        # Then list them
        list_recent = mock_mcp.registered_tools['list_recent_saves']
        result = await list_recent(5)
        
        # Verify response
        assert "📚 Recent Progress (2 items)" in result
        assert "First checkpoint" in result
        assert "Second checkpoint" in result
    
    @pytest.mark.asyncio
    async def test_list_recent_saves_empty(self, mock_server):
        """Test list_recent_saves when no checkpoints exist."""
        tool = CheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        list_recent = mock_mcp.registered_tools['list_recent_saves']
        result = await list_recent(5)
        
        assert result == "No saved progress found."
    
    @pytest.mark.asyncio
    async def test_search_checkpoints_no_results(self, mock_server):
        """Test search_checkpoints with no results."""
        tool = CheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        # Mock empty search results
        mock_server.search_engine.search.return_value = []
        
        search_checkpoints = mock_mcp.registered_tools['search_checkpoints']
        result = await search_checkpoints("nonexistent query", 10)
        
        assert "No checkpoints found for query: 'nonexistent query'" in result
        mock_server.search_engine.search.assert_called_with(
            query="nonexistent query",
            limit=10,
            doc_types=["checkpoint"]
        )


class TestTodoToolIntegration:
    """Test todo tool with real storage integration."""
    
    def test_tool_initialization(self, mock_server):
        """Test that todo tool initializes correctly."""
        tool = TodoTool(mock_server)
        
        assert tool.server == mock_server
        assert tool.config == mock_server.config
        assert tool.get_current_workspace() == "test_workspace"
    
    def test_tool_registration(self, mock_server):
        """Test that todo tools register correctly."""
        tool = TodoTool(mock_server)
        mock_mcp = MockMCPServer()
        
        tool.register(mock_mcp)
        
        # Verify expected tools were registered
        expected_tools = ['add_task', 'list_tasks', 'start_task', 'complete_task', 'search_todos']
        for tool_name in expected_tools:
            assert tool_name in mock_mcp.registered_tools
            assert callable(mock_mcp.registered_tools[tool_name])
    
    @pytest.mark.asyncio
    async def test_add_task_end_to_end(self, mock_server):
        """Test add_task function end-to-end with real storage."""
        tool = TodoTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        add_task = mock_mcp.registered_tools['add_task']
        
        # Test successful task addition
        result = await add_task("Write comprehensive unit tests")
        
        # Verify response
        assert "✅ Added task: Write comprehensive unit tests" in result
        assert "Task ID:" in result
        
        # Verify todo was actually saved
        pending_todos = mock_server.todo_storage.find_pending()
        assert len(pending_todos) == 1
        assert pending_todos[0].content == "Write comprehensive unit tests"
        assert pending_todos[0].workspace_id == "test_workspace"
        assert pending_todos[0].status == TodoStatus.PENDING
        
        # Verify search engine was called to index
        mock_server.search_engine.index_todo.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_tasks_with_data(self, mock_server):
        """Test list_tasks function with various todo states."""
        tool = TodoTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        # Add different types of tasks
        add_task = mock_mcp.registered_tools['add_task']
        start_task = mock_mcp.registered_tools['start_task']
        complete_task = mock_mcp.registered_tools['complete_task']
        
        await add_task("Pending task")
        await add_task("Active task")
        await add_task("Done task")
        
        # Get task IDs for manipulation
        all_todos = mock_server.todo_storage.find_pending()
        task_ids = [todo.id for todo in all_todos]
        
        # Start second task
        await start_task(task_ids[1])
        
        # Complete third task  
        await start_task(task_ids[2])
        await complete_task(task_ids[2])
        
        # List all tasks
        list_tasks = mock_mcp.registered_tools['list_tasks']
        result = await list_tasks()
        
        # Verify response structure
        assert "📋 **Your Tasks**" in result
        assert "🔄 **Working On" in result    # Should show active task
        assert "⏳ **To Do" in result         # Should show pending task
        assert "💡 Use 'start_task'" in result  # Should show help text
    
    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, mock_server):
        """Test list_tasks when no todos exist."""
        tool = TodoTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        list_tasks = mock_mcp.registered_tools['list_tasks']
        result = await list_tasks()
        
        # Should show empty message
        assert "📝 No active tasks" in result


class TestPlanToolIntegration:
    """Test plan tool with real storage integration."""
    
    def test_tool_initialization(self, mock_server):
        """Test that plan tool initializes correctly."""
        tool = PlanTool(mock_server)
        
        assert tool.server == mock_server
        assert tool.config == mock_server.config
        assert tool.get_current_workspace() == "test_workspace"
    
    def test_tool_registration(self, mock_server):
        """Test that plan tools register correctly."""
        tool = PlanTool(mock_server)
        mock_mcp = MockMCPServer()
        
        tool.register(mock_mcp)
        
        # Verify expected tools were registered
        expected_tools = ['create_plan', 'list_plans', 'activate_plan', 'complete_step']
        for tool_name in expected_tools:
            assert tool_name in mock_mcp.registered_tools
            assert callable(mock_mcp.registered_tools[tool_name])
    
    @pytest.mark.asyncio
    async def test_create_plan_end_to_end(self, mock_server):
        """Test create_plan function end-to-end with real storage."""
        tool = PlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        create_plan = mock_mcp.registered_tools['create_plan']
        
        # Test plan creation with steps
        result = await create_plan(
            "Test Implementation Plan",
            "Plan for implementing comprehensive tests",
            ["Write unit tests", "Add integration tests", "Improve coverage"]
        )
        
        # Verify response
        assert "📋 **Plan Created Successfully**" in result
        assert "**Title**: Test Implementation Plan" in result
        assert "**ID**: `" in result
        
        # Verify plan was actually saved
        recent_plans = mock_server.plan_storage.find_recent(limit=5)
        assert len(recent_plans) == 1
        
        plan = recent_plans[0]
        assert plan.title == "Test Implementation Plan"
        assert plan.description == "Plan for implementing comprehensive tests"
        assert plan.workspace_id == "test_workspace"
        assert plan.status == PlanStatus.DRAFT
        assert len(plan.steps) == 3
        assert plan.steps[0].description == "Write unit tests"
        
        # Verify search engine was called to index
        mock_server.search_engine.index_plan.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_activate_plan(self, mock_server):
        """Test plan activation functionality."""
        tool = PlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        # First create a plan
        create_plan = mock_mcp.registered_tools['create_plan']
        await create_plan("Activation Test Plan", "Test plan activation")
        
        # Get the plan ID
        recent_plans = mock_server.plan_storage.find_recent(limit=1)
        plan_id = recent_plans[0].id
        
        # Activate the plan
        activate_plan = mock_mcp.registered_tools['activate_plan']
        result = await activate_plan(plan_id)
        
        # Verify response
        assert "🚀 **Activated Plan**: Activation Test Plan" in result
        
        # Verify plan status changed
        updated_plan = mock_server.plan_storage.load(plan_id)
        assert updated_plan.status == PlanStatus.ACTIVE
        assert updated_plan.started_at is not None
    
    @pytest.mark.asyncio
    async def test_activate_nonexistent_plan(self, mock_server):
        """Test activating a plan that doesn't exist."""
        tool = PlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        activate_plan = mock_mcp.registered_tools['activate_plan']
        result = await activate_plan("nonexistent-plan-id")
        
        assert "❌ Plan nonexistent-plan-id not found" in result


class TestToolsErrorHandling:
    """Test error handling across all tools."""
    
    @pytest.mark.asyncio
    async def test_checkpoint_tool_storage_error(self, temp_config):
        """Test checkpoint tool handling storage errors."""
        mock_server = Mock()
        mock_server.config = temp_config
        
        # Mock storage that always fails
        mock_server.checkpoint_storage = Mock()
        mock_server.checkpoint_storage.save = Mock(return_value=False)
        mock_server.search_engine = Mock()
        
        tool = CheckpointTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        save_progress = mock_mcp.registered_tools['save_progress']
        result = await save_progress("Test checkpoint")
        
        assert "❌ Failed to save progress" in result
    
    @pytest.mark.asyncio
    async def test_todo_tool_storage_error(self, temp_config):
        """Test todo tool handling storage errors.""" 
        mock_server = Mock()
        mock_server.config = temp_config
        
        # Mock storage that always fails
        mock_server.todo_storage = Mock()
        mock_server.todo_storage.save = Mock(return_value=False)
        mock_server.search_engine = Mock()
        
        tool = TodoTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        add_task = mock_mcp.registered_tools['add_task']
        result = await add_task("Test task")
        
        assert "❌ Failed to add task" in result
    
    @pytest.mark.asyncio
    async def test_plan_tool_storage_error(self, temp_config):
        """Test plan tool handling storage errors."""
        mock_server = Mock()
        mock_server.config = temp_config
        
        # Mock storage that always fails
        mock_server.plan_storage = Mock()
        mock_server.plan_storage.save = Mock(return_value=False)
        mock_server.search_engine = Mock()
        
        tool = PlanTool(mock_server)
        mock_mcp = MockMCPServer()
        tool.register(mock_mcp)
        
        create_plan = mock_mcp.registered_tools['create_plan']
        result = await create_plan("Test Plan", "Test description")
        
        assert "❌ Failed to create plan" in result