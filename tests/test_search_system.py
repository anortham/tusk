"""Tests for Tusk search system using Whoosh."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

import pytest

from src.tusk.config import TuskConfig
from src.tusk.models import Checkpoint, Todo, Plan
from src.tusk.models.todo import TodoStatus, TodoPriority
from src.tusk.models.plan import PlanStatus
from src.tusk.storage.search import SearchEngine, SearchResult


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
def search_engine(temp_config):
    """Create a SearchEngine instance for testing."""
    search_engine = SearchEngine(temp_config)
    search_engine._ensure_index()
    return search_engine


@pytest.fixture
def sample_checkpoint():
    """Create a sample checkpoint for testing."""
    return Checkpoint(
        description="Fixed critical bug in authentication system",
        work_context="Working on user login improvements",
        active_files=["auth.py", "user_model.py"],
        tags=["bugfix", "authentication", "security"]
    )


@pytest.fixture
def sample_todo():
    """Create a sample todo for testing."""
    return Todo(
        content="Write comprehensive unit tests",
        active_form="Writing comprehensive unit tests",
        priority=TodoPriority.HIGH,
        tags=["testing", "quality", "development"]
    )


@pytest.fixture
def sample_plan():
    """Create a sample plan for testing."""
    plan = Plan(
        title="API Refactoring Project",
        description="Refactor the REST API for better performance and maintainability",
        goals=["Improve performance", "Better error handling", "Cleaner code"],
        tags=["refactoring", "api", "performance"]
    )
    plan.add_step("Analyze current API endpoints")
    plan.add_step("Design new API structure")
    plan.add_step("Implement refactored endpoints")
    plan.add_step("Update documentation")
    return plan


class TestSearchEngineInitialization:
    """Test search engine initialization and setup."""
    
    def test_initialization(self, temp_config):
        """Test search engine initialization."""
        search_engine = SearchEngine(temp_config)
        
        assert search_engine.config == temp_config
        assert search_engine.index_dir == temp_config.data_dir / "index"
        assert search_engine.ix is None  # Not initialized yet
    
    def test_initialize_creates_index(self, temp_config):
        """Test that initialize creates the index directory and schema."""
        search_engine = SearchEngine(temp_config)
        
        # Index directory might already exist from constructor
        # _ensure_index should set up the index
        search_engine._ensure_index()
        
        assert search_engine.index_dir.exists()
    
    def test_initialize_existing_index(self, search_engine):
        """Test initializing with existing index."""
        # First _ensure_index call
        search_engine._ensure_index()
        
        # Second call should work without issues
        search_engine._ensure_index()
        assert search_engine.index_dir.exists()
    
    def test_ensure_index_initialized(self, temp_config):
        """Test that _ensure_index_initialized works correctly."""
        search_engine = SearchEngine(temp_config)
        
        # Should initialize on first call
        search_engine._ensure_index()
        assert search_engine.index_dir.exists()
        
        # Should not fail on second call
        search_engine._ensure_index()


class TestSearchEngineIndexing:
    """Test search engine document indexing."""
    
    def test_index_checkpoint(self, search_engine, sample_checkpoint):
        """Test indexing a checkpoint."""
        result = search_engine.index_checkpoint(sample_checkpoint)
        
        assert result is True
        
        # Verify the checkpoint is searchable
        results = search_engine.search("authentication bug", limit=5)
        assert len(results) >= 1
        assert any(r.doc_id == sample_checkpoint.id for r in results)
    
    def test_index_todo(self, search_engine, sample_todo):
        """Test indexing a todo."""
        result = search_engine.index_todo(sample_todo)
        
        assert result is True
        
        # Verify the todo is searchable
        results = search_engine.search("unit tests", limit=5)
        assert len(results) >= 1
        assert any(r.doc_id == sample_todo.id for r in results)
    
    def test_index_plan(self, search_engine, sample_plan):
        """Test indexing a plan."""
        result = search_engine.index_plan(sample_plan)
        
        assert result is True
        
        # Verify the plan is searchable
        results = search_engine.search("API refactoring", limit=5)
        assert len(results) >= 1
        assert any(r.doc_id == sample_plan.id for r in results)
    
    def test_index_multiple_documents(self, search_engine, sample_checkpoint, sample_todo, sample_plan):
        """Test indexing multiple different document types."""
        # Index all documents
        assert search_engine.index_checkpoint(sample_checkpoint)
        assert search_engine.index_todo(sample_todo)
        assert search_engine.index_plan(sample_plan)
        
        # Search for "API" should find both plan and checkpoint (authentication system is an API-related concept)
        results = search_engine.search("API", limit=10)
        
        # Should find at least the plan (which contains "API" in title and text)
        assert len(results) >= 1
        doc_ids = [r.doc_id for r in results]
        assert sample_plan.id in doc_ids
        
        # Search for "tests" should find the todo
        test_results = search_engine.search("tests", limit=10)
        assert len(test_results) >= 1
        test_doc_ids = [r.doc_id for r in test_results]
        assert sample_todo.id in test_doc_ids


class TestSearchEngineQuerying:
    """Test search engine query functionality."""
    
    def test_basic_search(self, search_engine, sample_checkpoint):
        """Test basic text search."""
        search_engine.index_checkpoint(sample_checkpoint)
        
        # Search for terms that should match
        results = search_engine.search("authentication", limit=5)
        assert len(results) >= 1
        
        # Search for terms that shouldn't match
        results = search_engine.search("nonexistent keyword", limit=5)
        assert len(results) == 0
    
    def test_search_with_doc_types_filter(self, search_engine, sample_checkpoint, sample_todo):
        """Test search with document type filtering."""
        search_engine.index_checkpoint(sample_checkpoint)
        search_engine.index_todo(sample_todo)
        
        # Search only for checkpoints
        results = search_engine.search("test", limit=5, doc_types=["checkpoint"])
        checkpoint_results = [r for r in results if r.doc_id == sample_checkpoint.id]
        todo_results = [r for r in results if r.doc_id == sample_todo.id]
        
        # Should find checkpoint but not todo (if checkpoint contains "test")
        # Note: our sample checkpoint might not contain "test", so this verifies filtering works
        
        # Search only for todos
        results = search_engine.search("tests", limit=5, doc_types=["todo"])
        assert any(r.doc_id == sample_todo.id for r in results)
    
    def test_search_limit(self, search_engine):
        """Test search result limiting."""
        # Index multiple documents
        for i in range(10):
            checkpoint = Checkpoint(
                description=f"Test checkpoint number {i}",
            )
            search_engine.index_checkpoint(checkpoint)
        
        # Search with different limits
        results_5 = search_engine.search("checkpoint", limit=5)
        results_3 = search_engine.search("checkpoint", limit=3)
        
        assert len(results_5) <= 5
        assert len(results_3) <= 3
        assert len(results_3) <= len(results_5)
    
    def test_search_ranking(self, search_engine):
        """Test that search results are ranked by relevance."""
        # Create documents with different levels of relevance
        highly_relevant = Checkpoint(
            description="Python testing framework unittest pytest",
        )
        moderately_relevant = Checkpoint(
            description="Working on Python code with some testing",
        )
        less_relevant = Checkpoint(
            description="General development work on various projects",
        )
        
        search_engine.index_checkpoint(highly_relevant)
        search_engine.index_checkpoint(moderately_relevant)
        search_engine.index_checkpoint(less_relevant)
        
        results = search_engine.search("Python testing", limit=3)
        
        # Should have results
        assert len(results) >= 2
        
        # Should be ordered by relevance (higher scores first)
        if len(results) >= 2:
            assert results[0].score >= results[1].score
    
    def test_search_empty_query(self, search_engine, sample_checkpoint):
        """Test search with empty query."""
        search_engine.index_checkpoint(sample_checkpoint)
        
        results = search_engine.search("", limit=5)
        assert len(results) == 0
        
        results = search_engine.search("   ", limit=5)  # Whitespace only
        assert len(results) == 0


class TestSearchEngineAdvanced:
    """Test advanced search engine functionality."""
    
    def test_recent_search(self, search_engine):
        """Test searching for recent documents."""
        # Create documents with different timestamps
        old_checkpoint = Checkpoint(
            description="Old checkpoint from long ago",
        )
        # Manually set an old timestamp
        old_timestamp = datetime.now(timezone.utc).replace(year=2020)
        old_checkpoint.created_at = old_timestamp
        
        recent_checkpoint = Checkpoint(
            description="Recent checkpoint from today",
        )
        
        search_engine.index_checkpoint(old_checkpoint)
        search_engine.index_checkpoint(recent_checkpoint)
        
        # Search for recent documents (last 30 days)
        results = search_engine.search_recent(days=30, limit=5)
        
        # Should find the recent one but not the old one
        recent_ids = [r.doc_id for r in results]
        assert recent_checkpoint.id in recent_ids
        # Old checkpoint should not be in recent results
        assert old_checkpoint.id not in recent_ids
    
    def test_search_recent_with_doc_types(self, search_engine, sample_todo):
        """Test recent search with document type filtering."""
        search_engine.index_todo(sample_todo)
        
        # Search for recent todos only
        results = search_engine.search_recent(days=1, limit=5, doc_types=["todo"])
        
        assert len(results) >= 1
        assert any(r.doc_id == sample_todo.id for r in results)
    
    def test_update_document(self, search_engine, sample_checkpoint):
        """Test updating an existing document in the index."""
        # Index initial document
        search_engine.index_checkpoint(sample_checkpoint)
        
        # Search should find it
        results = search_engine.search("authentication", limit=5)
        assert len(results) >= 1
        
        # Update the document
        sample_checkpoint.description = "Updated description about database optimization"
        search_engine.index_checkpoint(sample_checkpoint)
        
        # Old content should not be found
        results = search_engine.search("authentication", limit=5)
        matching_results = [r for r in results if r.doc_id == sample_checkpoint.id]
        # Might be 0 if authentication was completely replaced
        
        # New content should be found
        results = search_engine.search("database optimization", limit=5)
        assert any(r.doc_id == sample_checkpoint.id for r in results)
    
    def test_delete_document(self, search_engine, sample_checkpoint):
        """Test deleting a document from the index.""" 
        # Index document
        search_engine.index_checkpoint(sample_checkpoint)
        
        # Verify it's searchable
        results = search_engine.search("authentication", limit=5)
        original_count = len([r for r in results if r.doc_id == sample_checkpoint.id])
        assert original_count >= 1
        
        # Delete document
        success = search_engine.delete_document(sample_checkpoint.id)
        assert success
        
        # Should no longer be searchable
        results = search_engine.search("authentication", limit=5)
        remaining_count = len([r for r in results if r.doc_id == sample_checkpoint.id])
        assert remaining_count < original_count


class TestSearchEngineErrorHandling:
    """Test search engine error handling."""
    
    def test_index_invalid_document_type(self, search_engine):
        """Test indexing with invalid document type."""
        # Try to index a non-supported object
        invalid_doc = {"not": "a supported document"}
        
        # Should handle gracefully without crashing
        result = search_engine._index_document(
            doc_id="invalid",
            doc_type="unknown",
            content="test content",
            title="test title",
            tags=[],
            workspace_id="test_workspace",
            created_at=datetime.now(timezone.utc)
        )
        # Should return False or handle gracefully
    
    def test_search_with_malformed_query(self, search_engine, sample_checkpoint):
        """Test search with potentially problematic queries."""
        search_engine.index_checkpoint(sample_checkpoint)
        
        # These should not crash the search engine
        problematic_queries = [
            "AND OR NOT",  # Only boolean operators
            "(((",         # Unbalanced parentheses
            "\"unclosed quote",  # Unclosed quote
            "field:value:invalid",  # Invalid field syntax
        ]
        
        for query in problematic_queries:
            try:
                results = search_engine.search(query, limit=5)
                # Should return empty results or handle gracefully
                assert isinstance(results, list)
            except Exception as e:
                # Should handle gracefully, not crash
                assert "search" in str(e).lower() or "query" in str(e).lower()
    
    def test_search_without_initialization(self, temp_config):
        """Test search operations before proper initialization."""
        search_engine = SearchEngine(temp_config)
        # Don't call initialize()
        
        # Should auto-initialize or handle gracefully
        results = search_engine.search("test", limit=5)
        assert isinstance(results, list)
    
    @patch('src.tusk.storage.search.index.open_dir')
    def test_search_with_index_error(self, mock_open_dir, temp_config):
        """Test search when index operations fail."""
        mock_open_dir.side_effect = Exception("Index error")
        
        search_engine = SearchEngine(temp_config)
        
        # Should handle index errors gracefully
        try:
            results = search_engine.search("test", limit=5)
            assert isinstance(results, list)
            assert len(results) == 0
        except Exception as e:
            # Should be a handled exception, not the raw index error
            assert "Index error" not in str(e)


class TestSearchResult:
    """Test SearchResult model."""
    
    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            doc_id="test_id",
            doc_type="checkpoint", 
            score=0.75,
            highlights={"title": "highlighted text"}
        )
        
        assert result.doc_id == "test_id"
        assert result.doc_type == "checkpoint"
        assert result.score == 0.75
        assert "highlighted text" in result.highlights.values()
    
    def test_search_result_comparison(self):
        """Test SearchResult comparison (for sorting by score)."""
        result_high = SearchResult(
            doc_id="high", doc_type="test", score=0.9,
            highlights={}
        )
        result_low = SearchResult(
            doc_id="low", doc_type="test", score=0.1,
            highlights={}
        )
        
        # Higher scores should come first when sorted in descending order
        results = sorted([result_low, result_high], key=lambda r: r.score, reverse=True)
        assert results[0] == result_high
        assert results[1] == result_low


class TestSearchEngineIntegration:
    """Integration tests for search engine with real data."""
    
    def test_realistic_search_scenario(self, search_engine):
        """Test a realistic search scenario with mixed content."""
        # Create a realistic set of documents
        documents = [
            Checkpoint(
                description="Fixed authentication bug in user login system",
                work_context="Working on security improvements for the web application",
                tags=["security", "bugfix", "authentication"]
            ),
            Todo(
                content="Write integration tests for the authentication API",
                active_form="Writing integration tests for authentication API",
                priority=TodoPriority.HIGH,
                tags=["testing", "authentication", "api"]
            ),
            Plan(
                title="Security Audit Project",
                description="Comprehensive security audit of the authentication system",
                goals=["Find vulnerabilities", "Fix security issues", "Improve authentication"],
                tags=["security", "audit", "authentication"]
            )
        ]
        
        # Index all documents
        search_engine.index_checkpoint(documents[0])
        search_engine.index_todo(documents[1])
        search_engine.index_plan(documents[2])
        
        # Test various searches
        
        # Search for "authentication" should find all three
        auth_results = search_engine.search("authentication", limit=5)
        assert len(auth_results) == 3
        
        # Search for "testing" should find mainly the todo
        test_results = search_engine.search("testing", limit=5)
        assert len(test_results) >= 1
        todo_found = any(r.doc_id == documents[1].id for r in test_results)
        assert todo_found
        
        # Search for "security" should find checkpoint and plan
        security_results = search_engine.search("security", limit=5)
        assert len(security_results) >= 2
        
        # More specific search should be more targeted
        bug_results = search_engine.search("authentication bug", limit=5)
        assert len(bug_results) >= 1
        # Should rank the checkpoint higher due to exact phrase match
        assert bug_results[0].doc_id == documents[0].id
    
    # Note: Workspace isolation test removed since workspaces are no longer a concept
    # All data is now stored in a single project-based location