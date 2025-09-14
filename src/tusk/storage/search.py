"""Whoosh-based search engine for Tusk memory."""

import logging
import random
import time
from datetime import UTC, datetime
from typing import Any

from whoosh import fields, index
from whoosh.qparser import MultifieldParser
from whoosh.writing import LockError

from ..config import TuskConfig
from ..models import Checkpoint, Plan, Task

logger = logging.getLogger(__name__)


class SearchResult:
    """A search result with score and metadata."""

    def __init__(self, doc_id: str, doc_type: str, score: float, highlights: dict[str, str]):
        self.doc_id = doc_id
        self.doc_type = doc_type  # 'checkpoint', 'task', 'plan'
        self.score = score
        self.highlights = highlights  # Field -> highlighted text

    def __str__(self) -> str:
        return f"{self.doc_type}:{self.doc_id} (score: {self.score:.2f})"


class SearchEngine:
    """Whoosh-based full-text search for Tusk memory."""

    def __init__(self, config: TuskConfig):
        self.config = config
        self.data_dir = config.get_data_dir()
        self.index_dir = self.data_dir / "index"
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Define schema
        self.schema = fields.Schema(
            # Document identification
            doc_id=fields.ID(stored=True, unique=True),
            doc_type=fields.ID(stored=True),  # checkpoint, task, plan
            # Main content fields
            title=fields.TEXT(stored=True, phrase=True),
            content=fields.TEXT(stored=True),
            description=fields.TEXT(stored=True),
            # Metadata fields
            status=fields.ID(stored=True),
            priority=fields.ID(stored=True),
            tags=fields.KEYWORD(stored=True, commas=True),
            # Time-based fields
            created_at=fields.DATETIME(stored=True),
            updated_at=fields.DATETIME(stored=True),
            # Relationship fields
            workspace_id=fields.ID(stored=True),
            checkpoint_id=fields.ID(stored=True),
            plan_id=fields.ID(stored=True),
            # Project tracking fields
            project_id=fields.ID(stored=True),
            project_path=fields.TEXT(stored=True),
            # File and context fields
            active_files=fields.KEYWORD(stored=True, commas=True),
            git_branch=fields.ID(stored=True),
            # Full search text (combination of all searchable content)
            search_text=fields.TEXT,
        )

        # Don't initialize index automatically for testing
        self.ix = None

    def _cleanup_stale_locks(self) -> None:
        """Remove stale lock files from the index directory."""
        try:
            for lock_file in self.index_dir.glob("*LOCK*"):
                if lock_file.is_file():
                    # Check if lock file is old (older than 5 minutes)
                    import time

                    file_age = time.time() - lock_file.stat().st_mtime
                    if file_age > 300:  # 5 minutes in seconds
                        lock_file.unlink()
                        logger.info(f"Removed stale lock file: {lock_file.name}")
        except Exception as e:
            logger.warning(f"Error cleaning up lock files: {e}")

    def _ensure_index(self) -> None:
        """Ensure the search index exists."""
        try:
            # Clean up any stale lock files first
            self._cleanup_stale_locks()

            if index.exists_in(str(self.index_dir)):
                self.ix = index.open_dir(str(self.index_dir))
                logger.debug("Opened existing search index")
            else:
                self.ix = index.create_in(str(self.index_dir), self.schema)
                logger.info("Created new search index")
        except Exception as e:
            logger.error(f"Error initializing search index: {e}")
            # Try cleaning locks and creating new index as fallback
            try:
                self._cleanup_stale_locks()
                self.ix = index.create_in(str(self.index_dir), self.schema)
                logger.info("Created new index after cleanup")
            except Exception as fallback_error:
                logger.error(f"Failed to create fallback index: {fallback_error}")
                self.ix = None

    def _safe_write(self, write_func, max_retries: int = 3) -> bool:  # type: ignore[no-untyped-def]
        """Safely write to index with retry logic for concurrent access."""
        for attempt in range(max_retries):
            try:
                if self.ix is None:
                    self._ensure_index()

                # If index is still None after initialization attempt, fail gracefully
                if self.ix is None:
                    logger.error("Search index initialization failed")
                    return False

                return write_func()

            except LockError:
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = 0.1 * (2**attempt) + random.uniform(0, 0.05)
                    time.sleep(delay)
                    logger.debug(f"Index write conflict, retrying in {delay:.2f}s")
                else:
                    logger.warning("Failed to write to index after retries")
                    return False
            except Exception as e:
                logger.error(f"Error during index write: {e}")
                return False

        return False

    def index_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Index a checkpoint for search."""

        def _write():  # type: ignore[no-untyped-def]
            # At this point, _safe_write guarantees ix is not None
            assert self.ix is not None
            writer = self.ix.writer()

            # Build search text
            search_parts = [
                checkpoint.description,
                checkpoint.work_context or "",
            ]
            search_parts.extend(checkpoint.active_files)
            search_parts.extend(checkpoint.tags)

            if checkpoint.git_branch:
                search_parts.append(checkpoint.git_branch)

            # Add highlight content
            for highlight in checkpoint.highlights:
                search_parts.append(highlight.to_search_text())

            writer.add_document(
                doc_id=checkpoint.id,
                doc_type="checkpoint",
                title=checkpoint.description[:100],  # First 100 chars as title
                content=checkpoint.work_context or "",
                description=checkpoint.description,
                status="",  # Checkpoints don't have status
                priority="",
                tags=",".join(checkpoint.tags),
                created_at=checkpoint.created_at,
                updated_at=checkpoint.updated_at,
                workspace_id=checkpoint.workspace_id,
                project_id=checkpoint.project_id,
                project_path=checkpoint.project_path,
                checkpoint_id="",
                plan_id="",
                active_files=",".join(checkpoint.active_files),
                git_branch=checkpoint.git_branch or "",
                search_text=" ".join(filter(None, search_parts)),
            )

            writer.commit()
            logger.debug(f"Indexed checkpoint {checkpoint.id}")
            return True

        return self._safe_write(_write)

    def index_task(self, task: Task) -> bool:
        """Index a task for search."""

        def _write():  # type: ignore[no-untyped-def]
            # At this point, _safe_write guarantees ix is not None
            assert self.ix is not None
            writer = self.ix.writer()

            search_parts = [
                task.content,
                task.active_form,
                task.status.value,
                task.priority.value,
            ]
            search_parts.extend(task.tags)

            if task.notes:
                search_parts.append(task.notes)

            writer.add_document(
                doc_id=task.id,
                doc_type="task",
                title=task.content,
                content=task.notes or "",
                description=task.content,
                status=task.status.value,
                priority=task.priority.value,
                tags=",".join(task.tags),
                created_at=task.created_at,
                updated_at=task.updated_at,
                workspace_id=task.workspace_id,
                project_id=task.project_id,
                project_path=task.project_path,
                checkpoint_id=task.checkpoint_id or "",
                plan_id=task.plan_id or "",
                active_files="",
                git_branch="",
                search_text=" ".join(filter(None, search_parts)),
            )

            writer.commit()
            logger.debug(f"Indexed task {task.id}")
            return True

        return self._safe_write(_write)

    def index_plan(self, plan: Plan) -> bool:
        """Index a plan for search."""

        def _write():  # type: ignore[no-untyped-def]
            # At this point, _safe_write guarantees ix is not None
            assert self.ix is not None
            writer = self.ix.writer()

            search_parts = [
                plan.title,
                plan.description,
                plan.status.value,
            ]
            search_parts.extend(plan.goals)
            search_parts.extend(plan.success_criteria)
            search_parts.extend(plan.tags)

            if hasattr(plan, "category") and plan.category:
                search_parts.append(plan.category)

            if hasattr(plan, "notes") and plan.notes:
                search_parts.append(plan.notes)

            # Add step descriptions
            for step in plan.steps:
                search_parts.append(step.description)
                if step.notes:
                    search_parts.append(step.notes)

            writer.add_document(
                doc_id=plan.id,
                doc_type="plan",
                title=plan.title,
                content=plan.description,
                description=plan.description,
                status=plan.status.value,
                priority="",  # Plans don't have priority in current model
                tags=",".join(plan.tags),
                created_at=plan.created_at,
                updated_at=plan.updated_at,
                workspace_id=plan.workspace_id,
                project_id=plan.project_id,
                project_path=plan.project_path,
                checkpoint_id="",
                plan_id="",
                active_files="",
                git_branch="",
                search_text=" ".join(filter(None, search_parts)),
            )

            writer.commit()
            logger.debug(f"Indexed plan {plan.id}")
            return True

        return self._safe_write(_write)

    def _index_document(  # type: ignore[no-untyped-def]
        self,
        doc_id: str,
        doc_type: str,
        content: str,
        title: str,
        tags: list[str],
        workspace_id: str,
        created_at: datetime,
        **kwargs,
    ) -> bool:
        """Generic document indexing method.

        This is a low-level method for testing and internal use.
        Prefer using the type-specific methods (index_checkpoint, etc.) for production.
        """
        if self.ix is None:
            self._ensure_index()

        # If index is still None after initialization attempt, fail gracefully
        if self.ix is None:
            logger.error("Search index initialization failed")
            return False

        try:
            writer = self.ix.writer()

            # Build document with defaults
            doc_fields = {
                "doc_id": doc_id,
                "doc_type": doc_type,
                "title": title,
                "content": content,
                "description": kwargs.get("description", title),
                "status": kwargs.get("status", ""),
                "priority": kwargs.get("priority", ""),
                "tags": ",".join(tags),
                "created_at": created_at,
                "updated_at": kwargs.get("updated_at", created_at),
                "workspace_id": workspace_id,
                "checkpoint_id": kwargs.get("checkpoint_id", ""),
                "plan_id": kwargs.get("plan_id", ""),
                "active_files": kwargs.get("active_files", ""),
                "git_branch": kwargs.get("git_branch", ""),
                "search_text": f"{title} {content} {' '.join(tags)}",
            }

            writer.add_document(**doc_fields)
            writer.commit()

            logger.debug(f"Indexed generic document {doc_id} of type {doc_type}")
            return True

        except Exception as e:
            logger.error(f"Error indexing document {doc_id}: {e}")
            return False

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the index."""
        if self.ix is None:
            self._ensure_index()

        # If index is still None after initialization attempt, fail gracefully
        if self.ix is None:
            logger.error("Search index initialization failed")
            return False

        try:
            writer = self.ix.writer()
            writer.delete_by_term("doc_id", doc_id)
            writer.commit()
            logger.debug(f"Removed document {doc_id} from index")
            return True
        except Exception as e:
            logger.error(f"Error removing document {doc_id}: {e}")
            return False

    def delete_document(self, doc_id: str) -> bool:
        """Alias for remove_document for backwards compatibility."""
        return self.remove_document(doc_id)

    def search(
        self,
        query: str,
        limit: int = 20,
        doc_types: list[str] | None = None,
        highlight: bool = True,
    ) -> list[SearchResult]:
        """Search across all indexed content."""
        if self.ix is None:
            self._ensure_index()

        # If index is still None after initialization attempt, return empty results
        if self.ix is None:
            logger.error("Search index initialization failed")
            return []

        try:
            with self.ix.searcher() as searcher:
                # Create parser for multiple fields
                parser = MultifieldParser(["title", "content", "description", "search_text"], schema=self.schema)

                # Parse the query
                parsed_query = parser.parse(query)

                # Add doc_type filter if specified
                if doc_types:
                    from whoosh.query import Or, Term

                    type_query = Or([Term("doc_type", dt) for dt in doc_types])
                    parsed_query = parsed_query & type_query

                # Execute search
                results = searcher.search(parsed_query, limit=limit)

                if highlight:
                    results.fragmenter.max_chars = 200
                    results.fragmenter.surround = 50

                search_results = []
                for hit in results:
                    highlights = {}
                    if highlight:
                        for field_name in ["title", "content", "description"]:
                            if field_name in hit:
                                highlighted = hit.highlights(field_name)
                                if highlighted:
                                    highlights[field_name] = highlighted

                    search_results.append(
                        SearchResult(
                            doc_id=hit["doc_id"],
                            doc_type=hit["doc_type"],
                            score=hit.score,
                            highlights=highlights,
                        )
                    )

                logger.debug(f"Search for '{query}' returned {len(search_results)} results")
                return search_results

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return []

    def search_cross_project(
        self,
        query: str = "*",
        limit: int = 50,
        doc_types: list[str] | None = None,
        project_ids: list[str] | None = None,
        days_back: int | None = None,
        highlight: bool = True,
    ) -> list[SearchResult]:
        """Search across projects with optional filtering."""
        if self.ix is None:
            self._ensure_index()

        # If index is still None after initialization attempt, return empty results
        if self.ix is None:
            logger.error("Search index initialization failed")
            return []

        try:
            with self.ix.searcher() as searcher:
                # Start with base query
                if query == "*" or not query:
                    from whoosh.query import Every

                    parsed_query = Every()
                else:
                    # Create parser for multiple fields
                    parser = MultifieldParser(["title", "content", "description", "search_text"], schema=self.schema)
                    parsed_query = parser.parse(query)

                # Add doc_type filter if specified
                if doc_types:
                    from whoosh.query import Or, Term

                    type_query = Or([Term("doc_type", dt) for dt in doc_types])
                    parsed_query = parsed_query & type_query

                # Add project filter if specified
                if project_ids:
                    from whoosh.query import Or, Term

                    project_query = Or([Term("project_id", pid) for pid in project_ids])
                    parsed_query = parsed_query & project_query

                # Add date filter if specified
                if days_back:
                    from datetime import datetime, timedelta

                    from whoosh.query import DateRange

                    threshold = datetime.now(UTC) - timedelta(days=days_back)
                    date_query = DateRange("created_at", threshold, None)
                    parsed_query = parsed_query & date_query

                # Execute search, sorted by date (newest first)
                results = searcher.search(parsed_query, limit=limit, sortedby="created_at", reverse=True)

                if highlight and query != "*":
                    results.fragmenter.max_chars = 200
                    results.fragmenter.surround = 50

                search_results = []
                for hit in results:
                    highlights = {}
                    if highlight and query != "*":
                        for field_name in ["title", "content", "description"]:
                            if field_name in hit:
                                highlighted = hit.highlights(field_name)
                                if highlighted:
                                    highlights[field_name] = highlighted

                    search_results.append(
                        SearchResult(
                            doc_id=hit["doc_id"],
                            doc_type=hit["doc_type"],
                            score=hit.score,
                            highlights=highlights,
                        )
                    )

                logger.debug(f"Cross-project search for '{query}' returned {len(search_results)} results")
                return search_results

        except Exception as e:
            logger.error(f"Error in cross-project search for '{query}': {e}")
            return []

    def search_by_tags(self, tags: list[str], limit: int = 20) -> list[SearchResult]:
        """Search by tags."""
        if not tags:
            return []

        # Build query for tags
        tag_query = " OR ".join(f"tags:{tag}" for tag in tags)
        return self.search(tag_query, limit=limit)

    def search_recent(self, days: int = 7, limit: int = 20, doc_types: list[str] | None = None) -> list[SearchResult]:
        """Search for recent documents."""
        from datetime import datetime, timedelta

        try:
            if self.ix is None:
                self._ensure_index()

            if self.ix is None:
                return []

            with self.ix.searcher() as searcher:
                # Calculate date threshold
                threshold = datetime.now(UTC) - timedelta(days=days)

                # Build query
                from whoosh.query import DateRange

                query = DateRange("created_at", threshold, None)

                # Add doc_type filter if specified
                if doc_types:
                    from whoosh.query import Or, Term

                    type_query = Or([Term("doc_type", dt) for dt in doc_types])
                    query = query & type_query

                # Execute search, sorted by date
                results = searcher.search(query, limit=limit, sortedby="created_at", reverse=True)

                search_results = []
                for hit in results:
                    search_results.append(
                        SearchResult(
                            doc_id=hit["doc_id"],
                            doc_type=hit["doc_type"],
                            score=hit.score,
                            highlights={},
                        )
                    )

                return search_results

        except Exception as e:
            logger.error(f"Error searching recent documents: {e}")
            return []

    def get_suggestions(self, partial_query: str, limit: int = 10) -> list[str]:
        """Get search suggestions based on partial query."""
        try:
            if self.ix is None:
                self._ensure_index()

            if self.ix is None:
                return []

            with self.ix.searcher() as searcher:
                # Use the title field for suggestions
                from whoosh.query import Prefix

                query = Prefix("title", partial_query.lower())

                results = searcher.search(query, limit=limit)
                suggestions = []

                for hit in results:
                    title = hit.get("title", "")
                    if title and title not in suggestions:
                        suggestions.append(title)

                return suggestions

        except Exception as e:
            logger.error(f"Error getting suggestions for '{partial_query}': {e}")
            return []

    def optimize_index(self) -> bool:
        """Optimize the search index for better performance."""
        try:
            if self.ix is None:
                self._ensure_index()

            if self.ix is None:
                return False

            writer = self.ix.writer()
            writer.commit(optimize=True)
            logger.info("Optimized search index")
            return True
        except Exception as e:
            logger.error(f"Error optimizing index: {e}")
            return False

    def get_index_stats(self) -> dict[str, Any]:
        """Get statistics about the search index."""
        try:
            if self.ix is None:
                self._ensure_index()

            if self.ix is None:
                return {}

            with self.ix.searcher() as searcher:
                stats = {
                    "total_docs": searcher.doc_count(),
                    "index_size_mb": self._get_index_size_mb(),
                }

                # Count by document type
                for doc_type in ["checkpoint", "todo", "plan"]:
                    from whoosh.query import Term

                    query = Term("doc_type", doc_type)
                    results = searcher.search(query, limit=None)
                    stats[f"{doc_type}_count"] = len(results)

                return stats

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}

    def _get_index_size_mb(self) -> float:
        """Calculate index size in MB."""
        try:
            total_size = 0
            for file_path in self.index_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0

    def cleanup_locks(self, force: bool = False) -> bool:
        """Manually clean up lock files.

        Args:
            force: If True, remove all lock files regardless of age.
                  If False, only remove files older than 5 minutes.

        Returns:
            True if any locks were removed, False otherwise.
        """
        removed_any = False
        try:
            for lock_file in self.index_dir.glob("*LOCK*"):
                if lock_file.is_file():
                    should_remove = force
                    if not force:
                        # Check if lock file is old
                        import time

                        file_age = time.time() - lock_file.stat().st_mtime
                        should_remove = file_age > 300  # 5 minutes

                    if should_remove:
                        lock_file.unlink()
                        logger.info(f"Removed lock file: {lock_file.name}")
                        removed_any = True

            return removed_any
        except Exception as e:
            logger.error(f"Error cleaning up lock files: {e}")
            return False
