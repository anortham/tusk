"""Comprehensive tests for Checkpoint and Highlight model functionality.

Tests the Checkpoint and Highlight models to ensure all functionality works correctly,
including highlight categorization, search text generation, and checkpoint context.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.tusk.models.checkpoint import Checkpoint, parse_ttl
from src.tusk.models.highlight import Highlight, HighlightCategory, HighlightImportance


class TestHighlightModel:
    """Test the Highlight model functionality."""

    def test_highlight_creation_minimal(self):
        """Test basic highlight creation with minimal fields."""
        highlight = Highlight(content="Fixed authentication bug")

        assert highlight.content == "Fixed authentication bug"
        assert highlight.category == HighlightCategory.GENERAL  # Default
        assert highlight.importance == HighlightImportance.MEDIUM  # Default
        assert highlight.timestamp is not None
        assert highlight.context is None
        assert len(highlight.tags) == 0
        assert len(highlight.related_files) == 0
        assert highlight.related_todo_id is None

    def test_highlight_creation_full(self):
        """Test highlight creation with all fields."""
        timestamp = datetime.now(timezone.utc)

        highlight = Highlight(
            content="Implemented OAuth2 integration with Auth0",
            category=HighlightCategory.COMPLETION,
            importance=HighlightImportance.HIGH,
            timestamp=timestamp,
            context="After 3 days of debugging, finally got the token refresh working",
            tags=["oauth2", "auth0", "authentication", "security"],
            related_files=["src/auth/oauth.py", "config/auth0.json"],
            related_todo_id="todo-123"
        )

        assert highlight.content == "Implemented OAuth2 integration with Auth0"
        assert highlight.category == HighlightCategory.COMPLETION
        assert highlight.importance == HighlightImportance.HIGH
        assert highlight.timestamp == timestamp
        assert highlight.context == "After 3 days of debugging, finally got the token refresh working"
        assert highlight.tags == ["oauth2", "auth0", "authentication", "security"]
        assert highlight.related_files == ["src/auth/oauth.py", "config/auth0.json"]
        assert highlight.related_todo_id == "todo-123"

    def test_highlight_categories(self):
        """Test all highlight categories."""
        categories = [
            HighlightCategory.DECISION,
            HighlightCategory.BREAKTHROUGH,
            HighlightCategory.BLOCKER,
            HighlightCategory.COMPLETION,
            HighlightCategory.INSIGHT,
            HighlightCategory.ERROR,
            HighlightCategory.REFACTOR,
            HighlightCategory.TODO,
            HighlightCategory.PLAN_STEP,
            HighlightCategory.DISCOVERY,
            HighlightCategory.GENERAL
        ]

        for category in categories:
            highlight = Highlight(
                content=f"Test content for {category.value}",
                category=category
            )
            assert highlight.category == category

    def test_highlight_importance_levels(self):
        """Test all importance levels."""
        importance_levels = [
            HighlightImportance.LOW,
            HighlightImportance.MEDIUM,
            HighlightImportance.HIGH,
            HighlightImportance.CRITICAL
        ]

        for importance in importance_levels:
            highlight = Highlight(
                content=f"Test content with {importance.value} importance",
                importance=importance
            )
            assert highlight.importance == importance

    def test_highlight_string_representation(self):
        """Test highlight string representation."""
        highlight = Highlight(
            content="This is a very long highlight content that should be truncated in the string representation because it's longer than 100 characters and we want to keep string representations concise",
            category=HighlightCategory.BREAKTHROUGH
        )

        str_repr = str(highlight)
        assert "[BREAKTHROUGH]" in str_repr
        assert "This is a very long highlight content" in str_repr
        assert "..." in str_repr  # Should be truncated

    def test_highlight_search_text_generation(self):
        """Test highlight search text generation."""
        highlight = Highlight(
            content="Discovered performance bottleneck in database queries",
            category=HighlightCategory.DISCOVERY,
            importance=HighlightImportance.HIGH,
            context="Query execution time went from 500ms to 50ms after adding index",
            tags=["performance", "database", "optimization"],
            related_files=["src/db/queries.sql", "src/models/user.py"]
        )

        search_text = highlight.to_search_text()

        # Verify all searchable content is included
        assert "Discovered performance bottleneck" in search_text
        assert "discovery" in search_text  # Category value
        assert "high" in search_text  # Importance value
        assert "Query execution time went from 500ms" in search_text
        assert "performance" in search_text
        assert "database" in search_text
        assert "optimization" in search_text
        assert "src/db/queries.sql" in search_text
        assert "src/models/user.py" in search_text


class TestCheckpointModel:
    """Test the Checkpoint model functionality."""

    def test_checkpoint_creation_minimal(self):
        """Test basic checkpoint creation with minimal required fields."""
        checkpoint = Checkpoint(description="Fixed user authentication bug")

        assert checkpoint.description == "Fixed user authentication bug"
        assert checkpoint.id is not None
        assert checkpoint.workspace_id == ""  # Default deprecated field
        assert checkpoint.project_id == ""  # Default
        assert checkpoint.project_path == ""  # Default
        assert checkpoint.session_id is None
        assert checkpoint.work_context is None
        assert len(checkpoint.active_files) == 0
        assert len(checkpoint.highlights) == 0
        assert checkpoint.git_branch is None
        assert checkpoint.git_commit is None
        assert checkpoint.is_global is False
        assert checkpoint.created_at is not None

    def test_checkpoint_creation_comprehensive(self):
        """Test checkpoint creation with all fields."""
        highlights = [
            Highlight(
                content="Fixed critical authentication bug",
                category=HighlightCategory.COMPLETION,
                importance=HighlightImportance.HIGH
            ),
            Highlight(
                content="Chose Auth0 over Firebase for OAuth implementation",
                category=HighlightCategory.DECISION,
                importance=HighlightImportance.MEDIUM
            )
        ]

        checkpoint = Checkpoint(
            description="Completed OAuth2 authentication implementation",
            workspace_id="workspace-123",  # Deprecated but still supported
            project_id="auth-project",
            project_path="/home/user/projects/auth-system",
            session_id="session-456",
            work_context="Successfully implemented OAuth2 with Auth0. Next: add 2FA support.",
            active_files=[
                "src/auth/oauth.py",
                "src/auth/routes.py",
                "tests/auth/test_oauth.py"
            ],
            highlights=highlights,
            git_branch="feature/oauth2-integration",
            git_commit="abc123def456",
            is_global=True
        )

        assert checkpoint.description == "Completed OAuth2 authentication implementation"
        assert checkpoint.workspace_id == "workspace-123"
        assert checkpoint.project_id == "auth-project"
        assert checkpoint.project_path == "/home/user/projects/auth-system"
        assert checkpoint.session_id == "session-456"
        assert checkpoint.work_context == "Successfully implemented OAuth2 with Auth0. Next: add 2FA support."
        assert len(checkpoint.active_files) == 3
        assert "src/auth/oauth.py" in checkpoint.active_files
        assert len(checkpoint.highlights) == 2
        assert checkpoint.git_branch == "feature/oauth2-integration"
        assert checkpoint.git_commit == "abc123def456"
        assert checkpoint.is_global is True

    def test_checkpoint_ttl_parsing(self):
        """Test TTL string parsing functionality."""
        # Test various TTL formats
        ttl_tests = [
            ("30m", timedelta(minutes=30)),
            ("2h", timedelta(hours=2)),
            ("7d", timedelta(days=7)),
            ("2w", timedelta(weeks=2)),
            ("", timedelta(days=7)),  # Default
            ("invalid", timedelta(days=7)),  # Default on parse error
            ("30", timedelta(days=7)),  # No unit, should default
            ("30x", timedelta(days=7)),  # Invalid unit, should default
        ]

        for ttl_str, expected_delta in ttl_tests:
            result = parse_ttl(ttl_str)
            assert result == expected_delta, f"Failed for TTL '{ttl_str}'"

    def test_checkpoint_with_highlights_integration(self):
        """Test checkpoint with various highlight types."""
        # Create highlights of different categories and importance
        highlights = [
            Highlight(
                content="Critical production bug identified",
                category=HighlightCategory.ERROR,
                importance=HighlightImportance.CRITICAL,
                tags=["bug", "production", "critical"]
            ),
            Highlight(
                content="Decided to refactor authentication module",
                category=HighlightCategory.DECISION,
                importance=HighlightImportance.MEDIUM,
                context="Current implementation is too tightly coupled"
            ),
            Highlight(
                content="Breakthrough: Found the root cause of memory leak",
                category=HighlightCategory.BREAKTHROUGH,
                importance=HighlightImportance.HIGH,
                related_files=["src/auth/session_manager.py"]
            ),
            Highlight(
                content="User authentication module completed",
                category=HighlightCategory.COMPLETION,
                importance=HighlightImportance.HIGH,
                related_todo_id="auth-implementation-todo"
            )
        ]

        checkpoint = Checkpoint(
            description="Major progress on authentication system",
            project_id="auth-system",
            highlights=highlights,
            work_context="Resolved critical issues and made significant progress"
        )

        # Verify all highlights are properly associated
        assert len(checkpoint.highlights) == 4

        # Check that we have all the expected categories
        categories = [h.category for h in checkpoint.highlights]
        assert HighlightCategory.ERROR in categories
        assert HighlightCategory.DECISION in categories
        assert HighlightCategory.BREAKTHROUGH in categories
        assert HighlightCategory.COMPLETION in categories

        # Check importance levels
        importance_levels = [h.importance for h in checkpoint.highlights]
        assert HighlightImportance.CRITICAL in importance_levels
        assert HighlightImportance.HIGH in importance_levels
        assert HighlightImportance.MEDIUM in importance_levels

    def test_checkpoint_search_context(self):
        """Test that checkpoints provide rich search context."""
        highlights = [
            Highlight(
                content="Implemented JWT token refresh mechanism",
                category=HighlightCategory.COMPLETION,
                tags=["jwt", "tokens", "auth"],
                context="Tokens now automatically refresh 5 minutes before expiry"
            ),
            Highlight(
                content="Database query optimization reduced load time by 80%",
                category=HighlightCategory.BREAKTHROUGH,
                tags=["performance", "database", "optimization"]
            )
        ]

        checkpoint = Checkpoint(
            description="Authentication system performance improvements",
            project_id="auth-perf-project",
            work_context="Focused on JWT implementation and database performance",
            active_files=[
                "src/auth/jwt_manager.py",
                "src/db/optimized_queries.py",
                "benchmarks/auth_performance.py"
            ],
            highlights=highlights,
            git_branch="feature/auth-performance"
        )

        # Verify the checkpoint contains rich searchable information
        assert checkpoint.description
        assert checkpoint.work_context
        assert len(checkpoint.active_files) > 0
        assert len(checkpoint.highlights) > 0
        assert checkpoint.git_branch

        # Check that highlights contain searchable content
        for highlight in checkpoint.highlights:
            assert highlight.content
            assert len(highlight.tags) > 0

    def test_checkpoint_project_tracking(self):
        """Test checkpoint project association and tracking."""
        checkpoint = Checkpoint(
            description="Initial project setup completed",
            project_id="new-microservice",
            project_path="/workspace/services/user-service",
            session_id="setup-session-001"
        )

        assert checkpoint.project_id == "new-microservice"
        assert checkpoint.project_path == "/workspace/services/user-service"
        assert checkpoint.session_id == "setup-session-001"

        # Test that workspace_id is deprecated but still works
        checkpoint_with_workspace = Checkpoint(
            description="Legacy workspace checkpoint",
            workspace_id="legacy-workspace-123",
            project_id="migrated-project"
        )

        assert checkpoint_with_workspace.workspace_id == "legacy-workspace-123"
        assert checkpoint_with_workspace.project_id == "migrated-project"

    def test_checkpoint_git_integration(self):
        """Test checkpoint Git context tracking."""
        checkpoint = Checkpoint(
            description="Feature implementation checkpoint",
            git_branch="feature/user-profiles",
            git_commit="a1b2c3d4e5f6",
            project_id="main-app"
        )

        assert checkpoint.git_branch == "feature/user-profiles"
        assert checkpoint.git_commit == "a1b2c3d4e5f6"

        # Test checkpoint without git info
        checkpoint_no_git = Checkpoint(
            description="Local development checkpoint",
            project_id="local-project"
        )

        assert checkpoint_no_git.git_branch is None
        assert checkpoint_no_git.git_commit is None

    def test_checkpoint_active_files_tracking(self):
        """Test tracking of active files in checkpoint."""
        active_files = [
            "src/components/UserProfile.tsx",
            "src/hooks/useUserData.ts",
            "src/services/userApi.ts",
            "src/types/user.ts",
            "tests/components/UserProfile.test.tsx"
        ]

        checkpoint = Checkpoint(
            description="User profile feature development",
            project_id="frontend-app",
            active_files=active_files
        )

        assert len(checkpoint.active_files) == 5
        assert "src/components/UserProfile.tsx" in checkpoint.active_files
        assert "tests/components/UserProfile.test.tsx" in checkpoint.active_files

        # Test checkpoint with no active files
        checkpoint_no_files = Checkpoint(
            description="Planning session",
            project_id="planning"
        )

        assert len(checkpoint_no_files.active_files) == 0


class TestHighlightCheckpointIntegration:
    """Test integration between Highlight and Checkpoint models."""

    def test_comprehensive_checkpoint_scenario(self):
        """Test a comprehensive real-world checkpoint scenario."""
        # Create a realistic set of highlights for a development session
        highlights = [
            Highlight(
                content="Started implementing user authentication system",
                category=HighlightCategory.PLAN_STEP,
                importance=HighlightImportance.MEDIUM,
                tags=["auth", "planning"],
                timestamp=datetime.now(timezone.utc) - timedelta(hours=2)
            ),
            Highlight(
                content="Encountered CORS issue with Auth0 integration",
                category=HighlightCategory.BLOCKER,
                importance=HighlightImportance.HIGH,
                context="Auth0 callback URL not working due to CORS policy",
                tags=["auth0", "cors", "blocker"],
                related_files=["src/auth/auth0.config.js"],
                timestamp=datetime.now(timezone.utc) - timedelta(hours=1, minutes=30)
            ),
            Highlight(
                content="Fixed CORS issue by updating Auth0 dashboard settings",
                category=HighlightCategory.COMPLETION,
                importance=HighlightImportance.HIGH,
                context="Added localhost:3000 to allowed callback URLs",
                tags=["auth0", "cors", "fix"],
                related_files=["src/auth/auth0.config.js"],
                timestamp=datetime.now(timezone.utc) - timedelta(hours=1)
            ),
            Highlight(
                content="Discovered that JWT tokens need custom claims for user roles",
                category=HighlightCategory.INSIGHT,
                importance=HighlightImportance.MEDIUM,
                context="Default Auth0 tokens don't include user role information",
                tags=["jwt", "roles", "auth0"],
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=30)
            ),
            Highlight(
                content="Successfully implemented role-based authentication",
                category=HighlightCategory.COMPLETION,
                importance=HighlightImportance.HIGH,
                context="Users can now be assigned admin, user, or guest roles",
                tags=["roles", "auth", "completion"],
                related_files=["src/auth/roles.js", "src/middleware/auth.js"],
                timestamp=datetime.now(timezone.utc)
            )
        ]

        checkpoint = Checkpoint(
            description="Completed role-based authentication implementation",
            project_id="saas-dashboard",
            project_path="/workspace/saas-dashboard",
            session_id="auth-implementation-session",
            work_context="Successfully implemented Auth0 integration with custom role-based access control. Ready for testing in staging environment.",
            active_files=[
                "src/auth/auth0.config.js",
                "src/auth/roles.js",
                "src/middleware/auth.js",
                "src/components/LoginButton.jsx",
                "src/hooks/useAuth.js",
                "tests/auth/auth.test.js"
            ],
            highlights=highlights,
            git_branch="feature/role-based-auth",
            git_commit="e4f5g6h7i8j9",
            is_global=False
        )

        # Verify the checkpoint captures the complete development story
        assert len(checkpoint.highlights) == 5
        assert checkpoint.project_id == "saas-dashboard"
        assert "Auth0 integration" in checkpoint.work_context
        assert len(checkpoint.active_files) == 6

        # Verify highlights tell the development story chronologically
        highlight_categories = [h.category for h in checkpoint.highlights]
        assert HighlightCategory.PLAN_STEP in highlight_categories
        assert HighlightCategory.BLOCKER in highlight_categories
        assert HighlightCategory.COMPLETION in highlight_categories
        assert HighlightCategory.INSIGHT in highlight_categories

        # Verify we can find different importance levels
        critical_highlights = [h for h in checkpoint.highlights if h.importance == HighlightImportance.HIGH]
        assert len(critical_highlights) == 3  # CORS issue, CORS fix, role completion

        # Verify tag-based organization
        auth_highlights = [h for h in checkpoint.highlights if "auth" in h.tags or "auth0" in h.tags]
        assert len(auth_highlights) >= 4

        # Verify file relationships
        auth_config_highlights = [h for h in checkpoint.highlights if "src/auth/auth0.config.js" in h.related_files]
        assert len(auth_config_highlights) == 2  # CORS issue and fix


if __name__ == "__main__":
    # Run a quick verification
    print("Running Checkpoint and Highlight model tests...")

    # Test basic functionality
    highlight = Highlight(
        content="Test highlight",
        category=HighlightCategory.COMPLETION,
        importance=HighlightImportance.HIGH
    )

    print(f"Highlight category: {highlight.category}")
    print(f"Highlight importance: {highlight.importance}")
    print(f"Highlight string: {str(highlight)}")

    # Test checkpoint with highlights
    checkpoint = Checkpoint(
        description="Test checkpoint",
        highlights=[highlight],
        project_id="test-project"
    )

    print(f"Checkpoint highlights: {len(checkpoint.highlights)}")
    print(f"Checkpoint project: {checkpoint.project_id}")

    # Test TTL parsing
    ttl_result = parse_ttl("7d")
    print(f"TTL parsing (7d): {ttl_result}")

    print("✅ Checkpoint and Highlight model tests completed successfully!")