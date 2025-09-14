"""All enhanced unified tools with rich parameter descriptions."""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import uuid4

from ..models.todo import Todo, TodoStatus, TodoPriority
from ..models.checkpoint import Checkpoint
from ..models.plan import Plan, PlanStatus, PlanStep
from .enhanced_base import EnhancedBaseTool

logger = logging.getLogger(__name__)


class EnhancedUnifiedCheckpointTool(EnhancedBaseTool):
    """Enhanced unified checkpoint tool with rich parameter descriptions."""

    def register(self, mcp_server) -> None:
        """Register the enhanced unified checkpoint tool."""

        @mcp_server.tool
        async def checkpoint(
            action: str,
            description: Optional[str] = None,
            limit: int = 5,
            query: Optional[str] = None
        ) -> str:
            """Save and retrieve work progress checkpoints.

            Checkpoints are like save points in your development journey, capturing
            important moments and progress that can be recalled later. Use them before
            risky changes, after achievements, at natural breaks, or when insights emerge.

            Args:
                action: The operation to perform. Valid values are "save" (create new checkpoint),
                    "list" (show recent checkpoints), "search" (find checkpoints by content).
                    This parameter is required.
                description: Progress description for saving checkpoints. Should be descriptive
                    and meaningful (e.g., "Fixed authentication bug in login system" or
                    "Completed user dashboard redesign"). Only required for action="save".
                limit: Maximum number of results to return for "list" and "search" actions.
                    Default 5, recommended range 3-20 to balance usefulness with readability.
                query: Search query text for finding checkpoints. Searches checkpoint descriptions
                    and related context. Use specific keywords for better results. Only used
                    with action="search".

            Returns:
                JSON response with checkpoint data, timestamps, and contextual information.
                Save operations return the new checkpoint details. List/search operations
                return arrays of matching checkpoints with relevance scoring.
            """
            try:
                if action == "save":
                    return await self._save_checkpoint(description)
                elif action == "list":
                    return await self._list_checkpoints(limit)
                elif action == "search":
                    return await self._search_checkpoints(query, limit)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Unknown action: {action}. Use: save, list, search"
                    }, ensure_ascii=False, indent=2)

            except Exception as e:
                logger.error(f"Checkpoint operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)

        # Enhance with parameter descriptions
        self.enhance_registered_tools(mcp_server, ['checkpoint'])

    async def _save_checkpoint(self, description: Optional[str]) -> str:
        """Save a progress checkpoint."""
        if not description:
            return json.dumps({
                "success": False,
                "error": "Description is required for save action"
            }, ensure_ascii=False, indent=2)

        # Get current project context
        project_id = self.config.get_current_project_id()
        project_path = self.config.get_current_project_path()

        checkpoint = Checkpoint(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            description=description,
            session_id=f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        )

        checkpoint.set_ttl(self.config.default_checkpoint_ttl)

        if self.checkpoint_storage.save(checkpoint):
            self.search_engine.index_checkpoint(checkpoint)
            logger.info(f"Created checkpoint {checkpoint.id}")

            return json.dumps({
                "success": True,
                "action": "progress_saved",
                "checkpoint": {
                    "id": checkpoint.id,
                    "description": description,
                    "project_id": checkpoint.project_id,
                    "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                    "session_id": checkpoint.session_id
                },
                "message": f"Saved progress: {description}",
                "encouragement": "Great work! Your progress is now safely captured."
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to save progress"
            }, ensure_ascii=False, indent=2)

    async def _list_checkpoints(self, limit: int) -> str:
        """List recent checkpoints."""
        checkpoints = self.checkpoint_storage.list_recent(limit)

        if not checkpoints:
            return json.dumps({
                "success": True,
                "total_checkpoints": 0,
                "checkpoints": [],
                "message": "No saved progress found.",
                "suggestion": "Use checkpoint(action='save', description='your achievement') to create one!"
            }, ensure_ascii=False, indent=2)

        checkpoints_data = [
            {
                "id": checkpoint.id,
                "description": checkpoint.description,
                "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                "project_id": checkpoint.project_id,
                "session_id": getattr(checkpoint, 'session_id', ''),
                "highlights_count": len(getattr(checkpoint, 'highlights', []))
            }
            for checkpoint in checkpoints
        ]

        return json.dumps({
            "success": True,
            "total_checkpoints": len(checkpoints),
            "checkpoints": checkpoints_data,
            "message": f"Found {len(checkpoints)} recent checkpoints",
            "suggestion": "Use checkpoint IDs to reference specific progress points"
        }, ensure_ascii=False, indent=2)

    async def _search_checkpoints(self, query: Optional[str], limit: int) -> str:
        """Search checkpoints by content."""
        if not query:
            return json.dumps({
                "success": False,
                "error": "Search query is required for search action"
            }, ensure_ascii=False, indent=2)

        results = self.search_engine.search(
            query=query,
            limit=limit,
            doc_types=["checkpoint"]
        )

        if not results:
            return json.dumps({
                "success": True,
                "query": query,
                "total_results": 0,
                "checkpoints": [],
                "message": f"No checkpoints found matching '{query}'",
                "suggestion": "Try broader search terms or use checkpoint(action='list') to see all checkpoints"
            }, ensure_ascii=False, indent=2)

        checkpoints_data = []
        for search_result in results:
            checkpoint = self.checkpoint_storage.load(search_result.doc_id)
            if checkpoint:
                checkpoints_data.append({
                    "id": checkpoint.id,
                    "description": checkpoint.description,
                    "created_at": checkpoint.created_at.strftime("%Y-%m-%d %H:%M"),
                    "project_id": checkpoint.project_id,
                    "session_id": getattr(checkpoint, 'session_id', ''),
                    "score": search_result.score,
                    "relevance": "High" if search_result.score > 0.8 else "Medium",
                    "highlights_count": len(getattr(checkpoint, 'highlights', []))
                })

        return json.dumps({
            "success": True,
            "query": query,
            "total_results": len(checkpoints_data),
            "checkpoints": checkpoints_data,
            "message": f"Found {len(checkpoints_data)} checkpoints matching '{query}'"
        }, ensure_ascii=False, indent=2)


class EnhancedUnifiedRecallTool(EnhancedBaseTool):
    """Enhanced unified recall tool with rich parameter descriptions."""

    def register(self, mcp_server) -> None:
        """Register the enhanced unified recall tool."""

        @mcp_server.tool
        async def recall(
            context: str = "recent",
            days_back: int = 7,
            session_id: Optional[str] = None,
            git_branch: Optional[str] = None
        ) -> str:
            """Smart memory recall - gets the context you need automatically.

            Recall retrieves your past work context to maintain continuity across sessions.
            This is essential for picking up where you left off and building on previous
            progress without losing important context or decisions.

            Args:
                context: What type of context to recall. Valid values are "recent" (last 2 days
                    of activity), "week" (past week summary), "session" (specific session by ID),
                    "branch" (git branch filtered), "all" (comprehensive history). Default "recent".
                days_back: Number of days to look back for context. Valid range 1-30 days.
                    Used with "week", "branch", and "all" contexts. Default 7 days.
                session_id: Specific session identifier to recall. Required when context="session".
                    Use previous recall results to find valid session IDs.
                git_branch: Git branch name to filter context by. Required when context="branch".
                    Useful for feature-specific work continuity.

            Returns:
                JSON response with comprehensive context including checkpoints, todos, plans,
                and session summaries. Includes timestamps, project associations, and
                relevance scoring to help prioritize information.
            """
            try:
                if context == "recent":
                    return await self._recall_recent()
                elif context == "week":
                    return await self._recall_timeframe(days_back)
                elif context == "session" and session_id:
                    return await self._recall_session(session_id)
                elif context == "branch" and git_branch:
                    return await self._recall_branch(git_branch, days_back)
                elif context == "all":
                    return await self._recall_comprehensive(days_back)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid context '{context}' or missing required parameters. "
                                 "Use: recent, week, session (with session_id), branch (with git_branch), all"
                    }, ensure_ascii=False, indent=2)

            except Exception as e:
                logger.error(f"Recall operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)

        # Enhance with parameter descriptions
        self.enhance_registered_tools(mcp_server, ['recall'])

    async def _recall_recent(self) -> str:
        """Quick recall of recent context (last 2 days)."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=2)

        # Get recent checkpoints
        recent_checkpoints = [
            cp for cp in self.checkpoint_storage.list_recent(10)
            if cp.created_at >= cutoff_date
        ]

        # Get active todos
        active_todos = self.todo_storage.get_active_todos()[:5]

        # Get recent plans
        recent_plans = [
            plan for plan in self.plan_storage.find_recent(5)
            if plan.created_at >= cutoff_date
        ]

        return json.dumps({
            "success": True,
            "context_type": "recent",
            "timeframe": "last 2 days",
            "summary": {
                "checkpoints_count": len(recent_checkpoints),
                "active_todos": len(active_todos),
                "recent_plans": len(recent_plans),
                "context_available": len(recent_checkpoints) > 0 or len(active_todos) > 0 or len(recent_plans) > 0
            },
            "checkpoints": [
                {
                    "id": cp.id,
                    "description": cp.description,
                    "created_at": cp.created_at.strftime("%Y-%m-%d %H:%M"),
                    "project_id": cp.project_id
                }
                for cp in recent_checkpoints[:3]
            ],
            "active_todos": [
                {
                    "id": todo.id,
                    "content": todo.content,
                    "status": todo.status.value,
                    "active_form": todo.active_form if hasattr(todo, 'active_form') else None
                }
                for todo in active_todos
            ],
            "recent_plans": [
                {
                    "id": plan.id,
                    "title": plan.title,
                    "status": plan.status.value,
                    "steps_completed": len([s for s in plan.steps if s.completed])
                }
                for plan in recent_plans
            ],
            "message": "Recent context loaded successfully" if (recent_checkpoints or active_todos or recent_plans) else "No recent context found"
        }, ensure_ascii=False, indent=2)

    async def _recall_timeframe(self, days_back: int) -> str:
        """Recall context for a specific timeframe."""
        return json.dumps({
            "success": True,
            "context_type": "timeframe",
            "days_back": days_back,
            "message": f"Context recall for {days_back} days back - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _recall_session(self, session_id: str) -> str:
        """Recall specific session context."""
        return json.dumps({
            "success": True,
            "context_type": "session",
            "session_id": session_id,
            "message": "Session-specific recall - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _recall_branch(self, git_branch: str, days_back: int) -> str:
        """Recall context filtered by git branch."""
        return json.dumps({
            "success": True,
            "context_type": "branch",
            "git_branch": git_branch,
            "days_back": days_back,
            "message": "Branch-filtered recall - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _recall_comprehensive(self, days_back: int) -> str:
        """Comprehensive context recall."""
        return json.dumps({
            "success": True,
            "context_type": "comprehensive",
            "days_back": days_back,
            "message": "Comprehensive recall - implementation needed"
        }, ensure_ascii=False, indent=2)


class EnhancedUnifiedPlanTool(EnhancedBaseTool):
    """Enhanced unified plan tool with rich parameter descriptions."""

    def register(self, mcp_server) -> None:
        """Register the enhanced unified plan tool."""

        @mcp_server.tool
        async def plan(
            action: str,
            title: Optional[str] = None,
            description: Optional[str] = None,
            plan_id: Optional[str] = None,
            step_description: Optional[str] = None,
            step_id: Optional[str] = None,
            query: Optional[str] = None,
            limit: int = 10
        ) -> str:
            """Plan complex work with structured multi-step approach.

            Plans help break down complex work into manageable steps, track progress
            across multiple sessions, and maintain alignment with users on project
            direction. Use plans for any work requiring coordination of multiple tasks.

            Args:
                action: The operation to perform. Valid values are "create" (new plan),
                    "list" (show plans), "activate" (set active plan), "complete" (finish plan),
                    "add_step" (add step to plan), "complete_step" (finish step),
                    "search" (find plans by content). This parameter is required.
                title: Plan title for creating new plans. Should be descriptive and
                    goal-oriented (e.g., "Implement user authentication system").
                    Only required for action="create".
                description: Detailed plan description explaining the overall goal, approach,
                    and expected outcomes. Used with action="create" for context.
                plan_id: The unique identifier of the plan to operate on. Required for
                    "activate", "complete", and "add_step" actions. Use action="list" to see plan IDs.
                step_description: Description of the step to add to a plan. Should be specific
                    and actionable (e.g., "Create user registration API endpoint"). Only used
                    with action="add_step".
                step_id: The unique identifier of the step to complete. Required for
                    action="complete_step". Use plan details to see step IDs.
                query: Search query text for finding plans. Searches plan titles, descriptions,
                    and step content. Use specific keywords for better results. Only used
                    with action="search".
                limit: Maximum number of results to return for "list" and "search" actions.
                    Default 10, recommended range 5-20 for optimal readability.

            Returns:
                JSON response with plan data including steps, progress tracking, and status
                information. Create operations return new plan details. List/search operations
                return arrays of plans with completion statistics and next actions.
            """
            try:
                if action == "create":
                    return await self._create_plan(title, description)
                elif action == "list":
                    return await self._list_plans(limit)
                elif action == "activate":
                    return await self._activate_plan(plan_id)
                elif action == "complete":
                    return await self._complete_plan(plan_id)
                elif action == "add_step":
                    return await self._add_step(plan_id, step_description)
                elif action == "complete_step":
                    return await self._complete_step(step_id)
                elif action == "search":
                    return await self._search_plans(query, limit)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Unknown action: {action}. Use: create, list, activate, complete, add_step, complete_step, search"
                    }, ensure_ascii=False, indent=2)

            except Exception as e:
                logger.error(f"Plan operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)

        # Enhance with parameter descriptions
        self.enhance_registered_tools(mcp_server, ['plan'])

    async def _create_plan(self, title: Optional[str], description: Optional[str]) -> str:
        """Create a new plan."""
        if not title:
            return json.dumps({
                "success": False,
                "error": "Title is required for create action"
            }, ensure_ascii=False, indent=2)

        # Get current project context
        project_id = self.config.get_current_project_id()
        project_path = self.config.get_current_project_path()

        plan = Plan(
            workspace_id="",
            project_id=project_id,
            project_path=project_path,
            title=title,
            description=description or "",
            status=PlanStatus.ACTIVE,
            steps=[]
        )

        if self.plan_storage.save(plan):
            self.search_engine.index_plan(plan)
            logger.info(f"Created plan {plan.id}")

            return json.dumps({
                "success": True,
                "action": "plan_created",
                "plan": {
                    "id": plan.id,
                    "title": title,
                    "description": description,
                    "status": plan.status.value,
                    "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M"),
                    "project_id": plan.project_id,
                    "steps_count": 0
                },
                "message": f"Created plan: {title}",
                "next_action": "Use plan(action='add_step', plan_id='{}', step_description='first step') to add steps".format(plan.id)
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to create plan"
            }, ensure_ascii=False, indent=2)

    async def _list_plans(self, limit: int) -> str:
        """List recent plans."""
        plans = self.plan_storage.find_recent(limit)

        if not plans:
            return json.dumps({
                "success": True,
                "total_plans": 0,
                "plans": [],
                "message": "No plans found.",
                "suggestion": "Use plan(action='create', title='your plan', description='details') to create one!"
            }, ensure_ascii=False, indent=2)

        plans_data = []
        for plan in plans:
            total_steps = len(plan.steps)
            completed_steps = len([s for s in plan.steps if s.completed])

            plans_data.append({
                "id": plan.id,
                "title": plan.title,
                "description": plan.description,
                "status": plan.status.value,
                "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M"),
                "project_id": plan.project_id,
                "progress": {
                    "total_steps": total_steps,
                    "completed_steps": completed_steps,
                    "progress_percent": (completed_steps / total_steps * 100) if total_steps > 0 else 0
                }
            })

        return json.dumps({
            "success": True,
            "total_plans": len(plans),
            "plans": plans_data,
            "message": f"Found {len(plans)} plans"
        }, ensure_ascii=False, indent=2)

    async def _activate_plan(self, plan_id: Optional[str]) -> str:
        """Activate a plan."""
        if not plan_id:
            return json.dumps({
                "success": False,
                "error": "Plan ID is required for activate action"
            }, ensure_ascii=False, indent=2)

        return json.dumps({
            "success": True,
            "action": "plan_activated",
            "plan_id": plan_id,
            "message": "Plan activation - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _complete_plan(self, plan_id: Optional[str]) -> str:
        """Complete a plan."""
        if not plan_id:
            return json.dumps({
                "success": False,
                "error": "Plan ID is required for complete action"
            }, ensure_ascii=False, indent=2)

        return json.dumps({
            "success": True,
            "action": "plan_completed",
            "plan_id": plan_id,
            "message": "Plan completion - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _add_step(self, plan_id: Optional[str], step_description: Optional[str]) -> str:
        """Add a step to a plan."""
        if not plan_id:
            return json.dumps({
                "success": False,
                "error": "Plan ID is required for add_step action"
            }, ensure_ascii=False, indent=2)

        if not step_description:
            return json.dumps({
                "success": False,
                "error": "Step description is required for add_step action"
            }, ensure_ascii=False, indent=2)

        return json.dumps({
            "success": True,
            "action": "step_added",
            "plan_id": plan_id,
            "step_description": step_description,
            "message": "Step addition - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _complete_step(self, step_id: Optional[str]) -> str:
        """Complete a plan step."""
        if not step_id:
            return json.dumps({
                "success": False,
                "error": "Step ID is required for complete_step action"
            }, ensure_ascii=False, indent=2)

        return json.dumps({
            "success": True,
            "action": "step_completed",
            "step_id": step_id,
            "message": "Step completion - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _search_plans(self, query: Optional[str], limit: int) -> str:
        """Search plans by content."""
        if not query:
            return json.dumps({
                "success": False,
                "error": "Search query is required for search action"
            }, ensure_ascii=False, indent=2)

        return json.dumps({
            "success": True,
            "query": query,
            "total_results": 0,
            "plans": [],
            "message": f"Plan search for '{query}' - implementation needed"
        }, ensure_ascii=False, indent=2)


class EnhancedUnifiedStandupTool(EnhancedBaseTool):
    """Enhanced unified standup tool with rich parameter descriptions."""

    def register(self, mcp_server) -> None:
        """Register the enhanced unified standup tool."""

        @mcp_server.tool
        async def standup(
            timeframe: str = "daily",
            include_completed: bool = True,
            days_back: int = 1
        ) -> str:
            """Generate a quick standup report of your recent work.

            Standup reports provide structured summaries of your progress, perfect for
            team updates, personal reflection, or understanding what you've accomplished
            across projects. Reports aggregate work from all projects and sessions.

            Args:
                timeframe: Report timeframe scope. Valid values are "daily" (last day),
                    "weekly" (past week), "custom" (specific days back). Default "daily"
                    provides focused recent progress.
                include_completed: Whether to include completed tasks and checkpoints in the
                    report. Set to False to focus only on ongoing work. Default True shows
                    comprehensive progress including achievements.
                days_back: Number of days to include in the report when timeframe="custom".
                    Valid range 1-14 days. Used only with custom timeframe. Default 1 day.

            Returns:
                JSON response with structured standup report including progress summaries,
                completed work, ongoing tasks, blockers, and recommendations for next steps.
                Reports are organized by project and include time-based progress tracking.
            """
            try:
                if timeframe == "daily":
                    return await self._generate_daily_standup(include_completed)
                elif timeframe == "weekly":
                    return await self._generate_weekly_standup(include_completed)
                elif timeframe == "custom":
                    return await self._generate_custom_standup(days_back, include_completed)
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid timeframe: {timeframe}. Use: daily, weekly, custom"
                    }, ensure_ascii=False, indent=2)

            except Exception as e:
                logger.error(f"Standup operation failed: {e}")
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False, indent=2)

        # Enhance with parameter descriptions
        self.enhance_registered_tools(mcp_server, ['standup'])

    async def _generate_daily_standup(self, include_completed: bool) -> str:
        """Generate daily standup report."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=1)

        # Get today's work
        recent_checkpoints = []
        if include_completed:
            recent_checkpoints = [
                cp for cp in self.checkpoint_storage.list_recent(10)
                if cp.created_at >= cutoff_date
            ]

        active_todos = self.todo_storage.get_active_todos()[:10]

        return json.dumps({
            "success": True,
            "report_type": "daily_standup",
            "timeframe": "last 24 hours",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "summary": {
                "achievements": len(recent_checkpoints),
                "ongoing_tasks": len([t for t in active_todos if t.status == TodoStatus.IN_PROGRESS]),
                "pending_tasks": len([t for t in active_todos if t.status == TodoStatus.PENDING]),
                "projects_active": len(set(cp.project_id for cp in recent_checkpoints)) if recent_checkpoints else 0
            },
            "achievements": [
                {
                    "description": cp.description,
                    "project_id": cp.project_id,
                    "completed_at": cp.created_at.strftime("%Y-%m-%d %H:%M")
                }
                for cp in recent_checkpoints[:5]
            ] if include_completed else [],
            "ongoing_work": [
                {
                    "content": todo.content,
                    "status": todo.status.value,
                    "active_form": getattr(todo, 'active_form', todo.content),
                    "project_id": todo.project_id
                }
                for todo in active_todos if todo.status == TodoStatus.IN_PROGRESS
            ],
            "next_actions": [
                {
                    "content": todo.content,
                    "priority": todo.priority.value,
                    "project_id": todo.project_id
                }
                for todo in active_todos if todo.status == TodoStatus.PENDING
            ][:3],
            "blockers": [],  # Would implement blocker detection
            "productivity_score": "High" if (recent_checkpoints or any(t.status == TodoStatus.IN_PROGRESS for t in active_todos)) else "Moderate"
        }, ensure_ascii=False, indent=2)

    async def _generate_weekly_standup(self, include_completed: bool) -> str:
        """Generate weekly standup report."""
        return json.dumps({
            "success": True,
            "report_type": "weekly_standup",
            "message": "Weekly standup generation - implementation needed"
        }, ensure_ascii=False, indent=2)

    async def _generate_custom_standup(self, days_back: int, include_completed: bool) -> str:
        """Generate custom timeframe standup report."""
        return json.dumps({
            "success": True,
            "report_type": "custom_standup",
            "days_back": days_back,
            "include_completed": include_completed,
            "message": "Custom standup generation - implementation needed"
        }, ensure_ascii=False, indent=2)