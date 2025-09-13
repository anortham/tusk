"""Tests for cross-project functionality and global storage."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models import Checkpoint, Todo, Plan
from src.tusk.storage import CheckpointStorage, TodoStorage, PlanStorage
from src.tusk.storage.search import SearchEngine
from src.tusk.models.todo import TodoStatus, TodoPriority
from src.tusk.models.plan import PlanStatus


class TestCrossProjectFunctionality:
    """Test cross-project functionality with global storage."""
    
    @pytest.fixture
    def temp_config(self):
        """Create a config with temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TuskConfig(
                storage_mode="global",
                data_dir=Path(temp_dir) / "tusk_data"
            )
            config.ensure_directories()
            yield config
    
    @pytest.fixture
    def storage_and_search(self, temp_config):
        """Create storage instances and search engine for testing."""
        checkpoint_storage = CheckpointStorage(temp_config)
        todo_storage = TodoStorage(temp_config)
        plan_storage = PlanStorage(temp_config)
        search_engine = SearchEngine(temp_config)
        search_engine._ensure_index()
        
        return {
            "config": temp_config,
            "checkpoint_storage": checkpoint_storage,
            "todo_storage": todo_storage,
            "plan_storage": plan_storage,
            "search_engine": search_engine
        }
    
    def test_project_field_population(self, storage_and_search):
        """Test that models are populated with correct project fields."""
        # Create models with explicit project context
        test_project_id = "test-project"
        test_project_path = "/path/to/test-project"
        
        checkpoint = Checkpoint(
            description="Test checkpoint",
            project_id=test_project_id,
            project_path=test_project_path
        )
        
        todo = Todo(
            content="Test todo",
            active_form="Testing todo",
            project_id=test_project_id,
            project_path=test_project_path
        )
        
        plan = Plan(
            title="Test plan",
            description="Test plan description",
            project_id=test_project_id,
            project_path=test_project_path
        )
        
        # Verify project fields are populated
        assert checkpoint.project_id == "test-project"
        assert checkpoint.project_path == "/path/to/test-project"
        assert todo.project_id == "test-project"
        assert todo.project_path == "/path/to/test-project"
        assert plan.project_id == "test-project"
        assert plan.project_path == "/path/to/test-project"
    
    def test_cross_project_search_no_filter(self, storage_and_search):
        """Test cross-project search without project filtering."""
        storages = storage_and_search
        search_engine = storages["search_engine"]
        
        # Create test data for multiple projects
        projects_data = [
            ("project-a", "/path/to/project-a"),
            ("project-b", "/path/to/project-b"),
            ("project-c", "/path/to/project-c")
        ]
        
        created_items = []
        
        for project_id, project_path in projects_data:
            # Create checkpoint
            checkpoint = Checkpoint(
                description=f"Checkpoint from {project_id}",
                project_id=project_id,
                project_path=project_path
            )
            storages["checkpoint_storage"].save(checkpoint)
            search_engine.index_checkpoint(checkpoint)
            created_items.append(("checkpoint", checkpoint.id, project_id))
            
            # Create todo
            todo = Todo(
                content=f"Todo from {project_id}",
                active_form=f"Working on {project_id}",
                project_id=project_id,
                project_path=project_path
            )
            storages["todo_storage"].save(todo)
            search_engine.index_todo(todo)
            created_items.append(("todo", todo.id, project_id))
            
            # Create plan
            plan = Plan(
                title=f"Plan from {project_id}",
                description=f"Plan description from {project_id}",
                project_id=project_id,
                project_path=project_path
            )
            storages["plan_storage"].save(plan)
            search_engine.index_plan(plan)
            created_items.append(("plan", plan.id, project_id))
        
        # Search across all projects
        results = search_engine.search_cross_project(
            query="*",  # Get everything
            limit=50
        )
        
        # Should find items from all projects
        assert len(results) == 9  # 3 projects × 3 items each
        
        # Verify we have items from all projects
        found_projects = set()
        for result in results:
            # Load the actual item to check project_id
            if result.doc_type == "checkpoint":
                item = storages["checkpoint_storage"].load(result.doc_id)
            elif result.doc_type == "todo":
                item = storages["todo_storage"].load(result.doc_id)
            elif result.doc_type == "plan":
                item = storages["plan_storage"].load(result.doc_id)
            
            if item:
                found_projects.add(item.project_id)
        
        assert found_projects == {"project-a", "project-b", "project-c"}
    
    def test_cross_project_search_with_project_filter(self, storage_and_search):
        """Test cross-project search with specific project filtering."""
        storages = storage_and_search
        search_engine = storages["search_engine"]
        
        # Create test data for multiple projects
        projects_data = [
            ("project-a", "/path/to/project-a"),
            ("project-b", "/path/to/project-b")
        ]
        
        for project_id, project_path in projects_data:
            checkpoint = Checkpoint(
                description=f"Important work in {project_id}",
                project_id=project_id,
                project_path=project_path
            )
            storages["checkpoint_storage"].save(checkpoint)
            search_engine.index_checkpoint(checkpoint)
        
        # Search only project-a
        results = search_engine.search_cross_project(
            query="Important work",
            project_ids=["project-a"],
            limit=50
        )
        
        # Should only find items from project-a
        assert len(results) == 1
        
        # Verify it's from the correct project
        checkpoint = storages["checkpoint_storage"].load(results[0].doc_id)
        assert checkpoint.project_id == "project-a"
        assert "project-a" in checkpoint.description
    
    def test_cross_project_search_with_multiple_project_filter(self, storage_and_search):
        """Test cross-project search filtering multiple specific projects."""
        storages = storage_and_search
        search_engine = storages["search_engine"]
        
        # Create test data for three projects
        projects = ["project-a", "project-b", "project-c"]
        
        for project_id in projects:
            checkpoint = Checkpoint(
                description=f"Checkpoint from {project_id}",
                project_id=project_id,
                project_path=f"/path/to/{project_id}"
            )
            storages["checkpoint_storage"].save(checkpoint)
            search_engine.index_checkpoint(checkpoint)
        
        # Search only project-a and project-c (exclude project-b)
        results = search_engine.search_cross_project(
            query="Checkpoint",
            project_ids=["project-a", "project-c"],
            limit=50
        )
        
        # Should find 2 items (project-a and project-c)
        assert len(results) == 2
        
        # Verify correct projects
        found_projects = set()
        for result in results:
            checkpoint = storages["checkpoint_storage"].load(result.doc_id)
            found_projects.add(checkpoint.project_id)
        
        assert found_projects == {"project-a", "project-c"}
        assert "project-b" not in found_projects
    
    def test_cross_project_search_with_date_filter(self, storage_and_search):
        """Test cross-project search with date filtering."""
        storages = storage_and_search
        search_engine = storages["search_engine"]
        
        # Create a recent checkpoint
        recent_checkpoint = Checkpoint(
            description="Recent work",
            project_id="test-project",
            project_path="/path/to/test-project"
        )
        storages["checkpoint_storage"].save(recent_checkpoint)
        search_engine.index_checkpoint(recent_checkpoint)
        
        # Search for recent items (last 7 days)
        results = search_engine.search_cross_project(
            query="*",
            days_back=7,
            limit=50
        )
        
        # Should find the recent checkpoint
        assert len(results) >= 1
        found = any(r.doc_id == recent_checkpoint.id for r in results)
        assert found
    
    def test_cross_project_search_performance(self, storage_and_search):
        """Test that cross-project search performs well with many items."""
        storages = storage_and_search
        search_engine = storages["search_engine"]
        
        # Create many items across multiple projects
        num_projects = 5
        items_per_project = 10
        
        for project_idx in range(num_projects):
            project_id = f"project-{project_idx}"
            project_path = f"/path/to/project-{project_idx}"
            
            for item_idx in range(items_per_project):
                checkpoint = Checkpoint(
                    description=f"Checkpoint {item_idx} from {project_id}",
                    project_id=project_id,
                    project_path=project_path
                )
                storages["checkpoint_storage"].save(checkpoint)
                search_engine.index_checkpoint(checkpoint)
        
        # Search across all projects
        import time
        start_time = time.time()
        
        results = search_engine.search_cross_project(
            query="Checkpoint",
            limit=100
        )
        
        search_time = time.time() - start_time
        
        # Should find all items quickly
        assert len(results) == num_projects * items_per_project
        assert search_time < 1.0  # Should complete in under 1 second
    
    def test_project_registry_functionality(self, temp_config):
        """Test project registry management."""
        config = temp_config
        
        # Test saving and loading registry
        registry = {
            "/path/to/project-a": "project-a",
            "/path/to/project-b": "project-b"
        }
        
        config.save_projects_registry(registry)
        loaded_registry = config.load_projects_registry()
        
        assert loaded_registry == registry
        
        # Test registering current project using patch at the class level
        with patch('src.tusk.config.TuskConfig.get_current_project_id', return_value='test-project'):
            with patch('src.tusk.config.TuskConfig.get_current_project_path', return_value='/path/to/test-project'):
                registered_id = config.register_current_project()
                assert registered_id == 'test-project'
                
                # Verify it was added to registry
                updated_registry = config.load_projects_registry()
                assert '/path/to/test-project' in updated_registry
                assert updated_registry['/path/to/test-project'] == 'test-project'
    
    def test_standup_cross_project_aggregation(self, storage_and_search):
        """Test that standup aggregates data from multiple projects."""
        storages = storage_and_search
        search_engine = storages["search_engine"]
        
        # Create work items across multiple projects
        projects = ["project-web", "project-api", "project-mobile"]
        
        for project_id in projects:
            # Create recent checkpoints (within last day)
            checkpoint = Checkpoint(
                description=f"Completed feature X in {project_id}",
                project_id=project_id,
                project_path=f"/path/to/{project_id}"
            )
            storages["checkpoint_storage"].save(checkpoint)
            search_engine.index_checkpoint(checkpoint)
            
            # Create recent todos
            todo = Todo(
                content=f"Implement feature Y in {project_id}",
                active_form=f"Implementing feature Y in {project_id}",
                status=TodoStatus.COMPLETED,
                project_id=project_id,
                project_path=f"/path/to/{project_id}"
            )
            storages["todo_storage"].save(todo)
            search_engine.index_todo(todo)
            
            # Create plans
            plan = Plan(
                title=f"Roadmap for {project_id}",
                description=f"Planning next features for {project_id}",
                status=PlanStatus.ACTIVE,
                project_id=project_id,
                project_path=f"/path/to/{project_id}"
            )
            storages["plan_storage"].save(plan)
            search_engine.index_plan(plan)
        
        # Search for recent work across all projects (simulating standup)
        results = search_engine.search_cross_project(
            query="*",  # Get everything
            days_back=1,  # Last day
            limit=100
        )
        
        # Should find items from all 3 projects
        assert len(results) == 9  # 3 projects × 3 items each
        
        # Verify we have data from all projects
        found_projects = set()
        item_types = set()
        
        for result in results:
            item_types.add(result.doc_type)
            # Load the actual item to check project_id
            if result.doc_type == "checkpoint":
                item = storages["checkpoint_storage"].load(result.doc_id)
            elif result.doc_type == "todo":
                item = storages["todo_storage"].load(result.doc_id)
            elif result.doc_type == "plan":
                item = storages["plan_storage"].load(result.doc_id)
            
            if item:
                found_projects.add(item.project_id)
        
        # Verify standup shows work from all projects
        assert found_projects == {"project-web", "project-api", "project-mobile"}
        assert item_types == {"checkpoint", "todo", "plan"}
        
        # Test that we can manually filter results by project (simulating what standup would do)
        # This tests the core standup functionality - getting cross-project data and then filtering it
        web_project_results = []
        for result in results:
            if result.doc_type == "checkpoint":
                item = storages["checkpoint_storage"].load(result.doc_id)
            elif result.doc_type == "todo":
                item = storages["todo_storage"].load(result.doc_id)
            elif result.doc_type == "plan":
                item = storages["plan_storage"].load(result.doc_id)
            
            if item and item.project_id == "project-web":
                web_project_results.append((result, item))
        
        # Should find exactly 3 items from project-web
        assert len(web_project_results) == 3, f"Expected 3 web project items but found {len(web_project_results)}"
        
        # Verify all found items are from project-web
        for result, item in web_project_results:
            assert item.project_id == "project-web"
        
        # Test that standup can aggregate specific types across projects
        checkpoint_results = []
        for result in results:
            if result.doc_type == "checkpoint":
                item = storages["checkpoint_storage"].load(result.doc_id)
                if item:
                    checkpoint_results.append(item)
        
        # Should find 3 checkpoints (one from each project)
        assert len(checkpoint_results) == 3
        checkpoint_projects = {cp.project_id for cp in checkpoint_results}
        assert checkpoint_projects == {"project-web", "project-api", "project-mobile"}
        
        # Close the search engine to release file locks
        if hasattr(search_engine, 'ix') and search_engine.ix:
            search_engine.ix.close()


class TestGlobalStorageMode:
    """Test global storage mode functionality."""
    
    def test_global_vs_local_storage_paths(self):
        """Test that global and local storage modes use different paths."""
        global_config = TuskConfig(storage_mode="global")
        local_config = TuskConfig(storage_mode="local")
        
        # Global mode should use home directory
        global_data_dir = global_config.get_data_dir()
        assert str(global_data_dir).startswith(str(Path.home()))
        # Use as_posix() to normalize path separators for cross-platform testing
        assert ".coa/tusk/data" in global_data_dir.as_posix()
        
        # Local mode should use current directory
        local_data_dir = local_config.get_data_dir()
        assert str(local_data_dir).startswith(str(Path.cwd()))
        # Use as_posix() to normalize path separators for cross-platform testing
        assert ".coa/tusk/data" in local_data_dir.as_posix()
        
        # They should be different
        assert global_data_dir != local_data_dir
    
    def test_project_detection(self):
        """Test automatic project detection."""
        config = TuskConfig()
        
        # Should detect current project
        project_id = config.get_current_project_id()
        project_path = config.get_current_project_path()
        
        assert isinstance(project_id, str)
        assert len(project_id) > 0
        assert isinstance(project_path, str)
        assert len(project_path) > 0
        
        # Project path should be absolute
        assert Path(project_path).is_absolute()
        
        # When in tusk directory, should detect "tusk" as project
        if "tusk" in str(Path.cwd()).lower():
            assert project_id == "tusk"
    
    def test_auto_detect_project_disabled(self):
        """Test behavior when auto project detection is disabled."""
        config = TuskConfig(auto_detect_project=False)
        
        project_id = config.get_current_project_id()
        assert project_id == "default"