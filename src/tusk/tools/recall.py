"""Recall tool for restoring session context."""

from datetime import timezone
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..models.checkpoint import Checkpoint
from ..models.plan import Plan
from ..models.todo import Todo, TodoStatus
from .base import BaseTool

logger = logging.getLogger(__name__)


class RecallTool(BaseTool):
    """Tool for intelligent session context restoration."""
    
    def register(self, mcp_server) -> None:
        """Register recall tools with the MCP server."""
        
        @mcp_server.tool
        async def recall(
            days_back: int = 7,
            include_todos: bool = True,
            include_plans: bool = True,
            include_checkpoints: bool = True,
            session_id: Optional[str] = None,
            git_branch: Optional[str] = None,
        ) -> str:
            """Restore persistent context from previous work sessions.
            
            BEHAVIORAL GUIDANCE: Use this tool at the start of each session to restore
            context and maintain continuity across sessions. Always prioritize this over
            starting fresh work without understanding existing context.
            
            DECISION LOGIC: Use broader time ranges when user mentions "what was I working on"
            or "where did I leave off". Use specific filters (session_id, git_branch) when
            context suggests focused work on particular topics.
            
            Args:
                days_back: How many days back to search for context (default 7)
                include_todos: Include active todos in recall (default True)
                include_plans: Include active plans in recall (default True) 
                include_checkpoints: Include recent checkpoints (default True)
                session_id: Filter to specific session context (optional)
                git_branch: Filter to specific git branch work (optional)
            """
            try:
                context = await self._build_recall_context(
                    days_back=days_back,
                    include_todos=include_todos,
                    include_plans=include_plans, 
                    include_checkpoints=include_checkpoints,
                    session_id=session_id,
                    git_branch=git_branch,
                )
                
                return self._format_recall_output(context)
                
            except Exception as e:
                logger.error(f"Error during recall: {e}")
                return f"❌ Error restoring context: {e}"
        
        @mcp_server.tool
        async def recall_session(session_id: str) -> str:
            """Recall context from a specific session.
            
            BEHAVIORAL GUIDANCE: Use when user references specific session ID or
            when you need to restore exact session state for debugging/continuation.
            """
            try:
                context = await self._build_recall_context(
                    days_back=30,  # Broader search for session-specific recall
                    include_todos=True,
                    include_plans=True,
                    include_checkpoints=True,
                    session_id=session_id,
                    git_branch=None,
                )
                return self._format_recall_output(context)
            except Exception as e:
                logger.error(f"Error during session recall: {e}")
                return f"❌ Error restoring session context: {e}"
        
        @mcp_server.tool
        async def recall_branch(git_branch: str, days_back: int = 14) -> str:
            """Recall context for work on a specific git branch.
            
            BEHAVIORAL GUIDANCE: Use when user mentions branch-specific work or
            when current git context suggests focused development on a branch.
            """
            try:
                context = await self._build_recall_context(
                    days_back=days_back,
                    include_todos=True,
                    include_plans=True,
                    include_checkpoints=True,
                    session_id=None,
                    git_branch=git_branch,
                )
                return self._format_recall_output(context)
            except Exception as e:
                logger.error(f"Error during branch recall: {e}")
                return f"❌ Error restoring branch context: {e}"
        
        @mcp_server.tool
        async def recall_quick() -> str:
            """Quick recall of the most recent context (last 2 days).
            
            BEHAVIORAL GUIDANCE: Use as default when user asks general questions
            about recent work. Faster and more focused than full recall.
            """
            try:
                context = await self._build_recall_context(
                    days_back=2,
                    include_todos=True,
                    include_plans=True,
                    include_checkpoints=True,
                    session_id=None,
                    git_branch=None,
                )
                return self._format_recall_output(context)
            except Exception as e:
                logger.error(f"Error during quick recall: {e}")
                return f"❌ Error restoring recent context: {e}"
    
    async def _build_recall_context(
        self,
        days_back: int,
        include_todos: bool,
        include_plans: bool,
        include_checkpoints: bool,
        session_id: Optional[str] = None,
        git_branch: Optional[str] = None,
    ) -> Dict:
        """Build the context information for recall."""
        
        context = {
            "workspace": self.get_current_workspace(),
            "recall_time": datetime.now(timezone.utc),
            "filter_applied": False,
            "checkpoints": [],
            "todos": [],
            "plans": [],
            "summary": {},
        }
        
        # Calculate time range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        # Get checkpoints
        if include_checkpoints:
            if session_id:
                context["checkpoints"] = self.checkpoint_storage.find_by_session(session_id)
                context["filter_applied"] = True
            elif git_branch:
                context["checkpoints"] = self.checkpoint_storage.find_by_git_branch(git_branch)
                context["filter_applied"] = True
            else:
                context["checkpoints"] = self.checkpoint_storage.list_by_date_range(start_date, end_date)
        
        # Get todos
        if include_todos:
            all_todos = self.todo_storage.get_active_todos()
            
            # Filter todos by timeframe or specific criteria
            if session_id or git_branch:
                # For specific filters, get all active todos
                context["todos"] = all_todos
            else:
                # For time-based, filter by creation/update time
                filtered_todos = []
                for todo in all_todos:
                    # All datetimes are now timezone-aware
                    if (todo.created_at >= start_date or 
                        (todo.updated_at and todo.updated_at >= start_date)):
                        filtered_todos.append(todo)
                context["todos"] = filtered_todos
        
        # Get plans
        if include_plans:
            active_plans = self.plan_storage.find_active()
            
            # Filter similar to todos
            if session_id or git_branch:
                context["plans"] = active_plans
            else:
                filtered_plans = []
                for plan in active_plans:
                    # All datetimes are now timezone-aware
                    if (plan.created_at >= start_date or 
                        (plan.updated_at and plan.updated_at >= start_date)):
                        filtered_plans.append(plan)
                context["plans"] = filtered_plans
        
        # Build summary stats
        context["summary"] = {
            "checkpoints_count": len(context["checkpoints"]),
            "todos_count": len(context["todos"]),
            "active_todos": len([t for t in context["todos"] if t.status == TodoStatus.IN_PROGRESS]),
            "pending_todos": len([t for t in context["todos"] if t.status == TodoStatus.PENDING]),
            "plans_count": len(context["plans"]),
            "days_covered": days_back,
            "session_filter": session_id,
            "branch_filter": git_branch,
        }
        
        return context
    
    def _format_recall_output(self, context: Dict) -> str:
        """Format the recall context into a readable summary."""
        
        recall_time = context["recall_time"].strftime("%Y-%m-%d %H:%M")
        workspace = context["workspace"]
        summary = context["summary"]
        
        # Header
        result = f"🐘 **Tusk Memory Recall** - {recall_time}\\n"
        result += f"📁 **Workspace**: {workspace}\\n\\n"
        
        # Filters applied
        if context["filter_applied"]:
            if summary["session_filter"]:
                result += f"🔍 **Session Filter**: {summary['session_filter']}\\n"
            if summary["branch_filter"]:
                result += f"🔍 **Branch Filter**: {summary['branch_filter']}\\n"
            result += "\\n"
        
        # Summary stats
        result += f"📊 **Context Summary**\\n"
        result += f"- {summary['checkpoints_count']} checkpoints from last {summary['days_covered']} days\\n"
        result += f"- {summary['todos_count']} active todos ({summary['active_todos']} in progress, {summary['pending_todos']} pending)\\n"
        result += f"- {summary['plans_count']} active plans\\n\\n"
        
        # No context found
        if (summary["checkpoints_count"] == 0 and 
            summary["todos_count"] == 0 and 
            summary["plans_count"] == 0):
            result += "💭 **No recent context found**\\n"
            result += "This might be a fresh start! Create a checkpoint to begin tracking your work.\\n"
            return result
        
        # Recent checkpoints
        if context["checkpoints"]:
            result += f"## 📚 Recent Checkpoints ({len(context['checkpoints'])})\\n\\n"
            
            # Show most recent first, limit to 5 for readability
            recent_checkpoints = sorted(context["checkpoints"], key=lambda c: c.created_at, reverse=True)[:5]
            
            for i, checkpoint in enumerate(recent_checkpoints, 1):
                created = checkpoint.created_at.strftime("%m-%d %H:%M")
                result += f"**{i}. [{created}] {checkpoint.description}**\\n"
                
                # Show highlights if any
                if checkpoint.highlights:
                    result += f"   💡 {len(checkpoint.highlights)} highlights:\\n"
                    # Show first 2 highlights
                    for highlight in checkpoint.highlights[:2]:
                        result += f"      • [{highlight.category.value}] {highlight.content[:80]}...\\n"
                
                # Show context if available
                if checkpoint.work_context:
                    context_preview = checkpoint.work_context[:100].replace('\\n', ' ')
                    result += f"   📝 {context_preview}...\\n"
                
                result += "\\n"
        
        # Active todos
        if context["todos"]:
            result += f"## ✅ Active Todos ({len(context['todos'])})\\n\\n"
            
            # Group by status
            in_progress = [t for t in context["todos"] if t.status == TodoStatus.IN_PROGRESS]
            pending = [t for t in context["todos"] if t.status == TodoStatus.PENDING]
            
            if in_progress:
                result += f"**🔄 In Progress ({len(in_progress)}):**\\n"
                for todo in in_progress[:3]:  # Limit for readability
                    result += f"- {todo.get_display_form()}\\n"
                result += "\\n"
            
            if pending:
                result += f"**⏳ Pending ({len(pending)}):**\\n"
                for todo in pending[:5]:  # Show more pending items
                    result += f"- {todo.content}\\n"
                result += "\\n"
        
        # Active plans
        if context["plans"]:
            result += f"## 📋 Active Plans ({len(context['plans'])})\\n\\n"
            
            for plan in context["plans"][:3]:  # Limit for readability
                completed, total = plan.get_progress()
                progress = f"({completed}/{total})"
                
                result += f"**{plan.title}** {progress}\\n"
                result += f"   📝 {plan.description[:100]}...\\n"
                
                # Show next steps
                next_steps = plan.get_next_steps(2)
                if next_steps:
                    result += f"   🎯 Next: {next_steps[0].description}\\n"
                
                result += "\\n"
        
        # Suggestions for next actions
        result += "## 🎯 Suggested Next Actions\\n\\n"
        
        if summary["active_todos"] > 0:
            result += "- Continue with in-progress todos\\n"
        
        if summary["pending_todos"] > 0:
            result += "- Pick up pending todos\\n"
        
        if context["plans"]:
            result += "- Work on next steps in active plans\\n"
        
        if context["checkpoints"]:
            result += "- Create a new checkpoint when you complete significant work\\n"
        
        result += "- Use search tools to find specific information\\n"
        
        return result