"""Simplified tool interfaces using FastMCP transformations.

This module creates beginner-friendly versions of Tusk tools with hidden complexity
and smart defaults. All tools route to the same underlying functions but provide
simplified interfaces that reduce cognitive load for the AI.
"""

from fastmcp.tools import Tool
from datetime import datetime, timezone
import logging
from typing import Dict, Any
from ..models.checkpoint import Checkpoint
from ..models.todo import Todo, TodoPriority, TodoStatus
from ..models.plan import Plan

logger = logging.getLogger(__name__)


class SimplifiedTools:
    """Simplified tools with smart defaults and hidden complexity."""
    
    def __init__(self, tusk_server):
        self.server = tusk_server
        self.config = tusk_server.config
        self.checkpoint_storage = tusk_server.checkpoint_storage
        self.todo_storage = tusk_server.todo_storage
        self.plan_storage = tusk_server.plan_storage
        self.search_engine = tusk_server.search_engine
    
    def get_current_workspace(self) -> str:
        """Get current workspace ID."""
        return self.config.current_workspace
    
    def register_simplified_tools(self, mcp_server) -> None:
        """Register simplified tools with the MCP server."""
        
        # 1. SAVE - Simple checkpoint creation (already simple)
        @mcp_server.tool
        async def save(description: str) -> str:
            """Save your current work progress.
            
            BEHAVIORAL GUIDANCE: Use when completing significant work or reaching
            stopping points. Creates a checkpoint you can recall later.
            """
            try:
                checkpoint = Checkpoint(
                    workspace_id=self.get_current_workspace(),
                    description=description,
                    session_id=f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                )
                
                checkpoint.set_ttl(self.config.default_checkpoint_ttl)
                
                if self.checkpoint_storage.save(checkpoint):
                    self.search_engine.index_checkpoint(checkpoint)
                    logger.info(f"Created checkpoint {checkpoint.id}")
                    return f"✅ Saved: {description}\\n\\nID: {checkpoint.id}"
                else:
                    return f"❌ Failed to save progress"
                    
            except Exception as e:
                logger.error(f"Error saving progress: {e}")
                return f"❌ Error saving: {e}"
        
        # 2. RECALL - Smart context restoration
        @mcp_server.tool
        async def recall(context: str = "recent") -> str:
            """Smart memory recall - gets the context you need automatically.
            
            BEHAVIORAL GUIDANCE: Your primary tool for session continuity.
            Use at start of sessions or when you need to understand recent work.
            
            Args:
                context: What to recall:
                - "recent" (default): Last 2 days
                - "week": Last 7 days
                - "all": Everything from workspace
                - "session_ID": Specific session
                - "branch_NAME": Git branch work
            """
            try:
                # Parse context and call appropriate recall method
                if context == "recent" or context == "":
                    return await self._recall_quick()
                elif context == "week":
                    return await self._recall_context(days_back=7)
                elif context == "all":
                    return await self._recall_context(days_back=30)
                elif context.startswith("session_"):
                    session_id = context.replace("session_", "")
                    return await self._recall_session(session_id)
                elif context.startswith("branch_"):
                    branch_name = context.replace("branch_", "")
                    return await self._recall_branch(branch_name)
                else:
                    return await self._recall_quick()
            except Exception as e:
                logger.error(f"Error in recall: {e}")
                return f"❌ Error recalling context: {e}"
        
        # 3. TODO - Quick task addition (already simple)
        @mcp_server.tool
        async def todo(task: str) -> str:
            """Add a task to your persistent todo list.
            
            BEHAVIORAL GUIDANCE: Use for any actionable items that need to be
            tracked across sessions. Captures work that persists beyond current context.
            """
            try:
                todo = Todo(
                    workspace_id=self.get_current_workspace(),
                    content=task,
                    active_form=f"Working on {task.lower()}",
                    priority=TodoPriority.MEDIUM,
                    status=TodoStatus.PENDING,
                )
                
                if self.todo_storage.save(todo):
                    self.search_engine.index_todo(todo)
                    logger.info(f"Created todo {todo.id}")
                    return f"✅ Added: {task}\\n\\nID: {todo.id}"
                else:
                    return "❌ Failed to add task"
                    
            except Exception as e:
                logger.error(f"Error adding task: {e}")
                return f"❌ Error adding task: {e}"
        
        # 4. SEARCH - Universal search across all data
        @mcp_server.tool
        async def search(query: str, scope: str = "all") -> str:
            """Search all your work data - finds checkpoints, todos, and plans.
            
            BEHAVIORAL GUIDANCE: Use when user asks about specific topics,
            decisions, or past work. More precise than browsing lists.
            
            Args:
                query: What to search for
                scope: Where to search ("all", "checkpoints", "todos", "plans")
            """
            try:
                results = []
                
                # Search checkpoints
                if scope in ["all", "checkpoints"]:
                    checkpoint_results = self.search_engine.search(
                        query=query, limit=5, doc_types=["checkpoint"]
                    )
                    for result in checkpoint_results:
                        checkpoint = self.checkpoint_storage.load(result.doc_id)
                        if checkpoint:
                            results.append({
                                "type": "checkpoint",
                                "score": result.score,
                                "title": checkpoint.description,
                                "id": checkpoint.id,
                                "date": checkpoint.created_at.strftime("%m-%d %H:%M")
                            })
                
                # Search todos
                if scope in ["all", "todos"]:
                    todo_results = self.search_engine.search(
                        query=query, limit=5, doc_types=["todo"]
                    )
                    for result in todo_results:
                        todo = self.todo_storage.load(result.doc_id)
                        if todo:
                            results.append({
                                "type": "todo",
                                "score": result.score,
                                "title": todo.content,
                                "id": todo.id,
                                "status": todo.status.value
                            })
                
                # Search plans
                if scope in ["all", "plans"]:
                    plan_results = self.search_engine.search(
                        query=query, limit=5, doc_types=["plan"]
                    )
                    for result in plan_results:
                        plan = self.plan_storage.load(result.doc_id)
                        if plan:
                            results.append({
                                "type": "plan",
                                "score": result.score,
                                "title": plan.title,
                                "id": plan.id,
                                "progress": f"{plan.get_progress()[0]}/{plan.get_progress()[1]}"
                            })
                
                if not results:
                    return f"🔍 No results found for '{query}' in {scope}"
                
                # Sort by score and format output
                results.sort(key=lambda x: x["score"], reverse=True)
                
                output = f"🔍 **Search Results for '{query}'** ({len(results)} found)\\n\\n"
                
                for i, result in enumerate(results[:8], 1):
                    icon = {"checkpoint": "📚", "todo": "✅", "plan": "📋"}.get(result["type"], "📄")
                    output += f"**{i}. {icon} {result['title']}** (score: {result['score']:.2f})\\n"
                    output += f"   Type: {result['type'].title()}"
                    
                    if result["type"] == "checkpoint":
                        output += f" | Created: {result['date']}"
                    elif result["type"] == "todo":
                        output += f" | Status: {result['status']}"
                    elif result["type"] == "plan":
                        output += f" | Progress: {result['progress']}"
                    
                    output += f"\\n   ID: `{result['id']}`\\n\\n"
                
                return output
                
            except Exception as e:
                logger.error(f"Error in search: {e}")
                return f"❌ Error searching: {e}"
        
        # 5. COMPLETE - Mark tasks as done
        @mcp_server.tool
        async def complete(task_id: str) -> str:
            """Mark a task as completed.
            
            BEHAVIORAL GUIDANCE: Use when task is fully accomplished.
            Creates closure and maintains accurate state for future sessions.
            """
            try:
                todo = self.todo_storage.load(task_id)
                if not todo:
                    return f"❌ Task not found: {task_id}"
                
                if todo.status == TodoStatus.COMPLETED:
                    return f"ℹ️ Task already completed: {todo.content}"
                
                todo.status = TodoStatus.COMPLETED
                todo.completed_at = datetime.now(timezone.utc)
                
                if self.todo_storage.save(todo):
                    logger.info(f"Completed todo {todo.id}")
                    return f"✅ Completed: {todo.content}"
                else:
                    return "❌ Failed to mark task as completed"
                    
            except Exception as e:
                logger.error(f"Error completing task: {e}")
                return f"❌ Error completing task: {e}"
        
        # 6. PLAN - Simple planning
        @mcp_server.tool
        async def plan(title: str, description: str = "", steps: str = "") -> str:
            """Create a multi-step plan to organize complex work.
            
            BEHAVIORAL GUIDANCE: Use when user mentions multi-step projects
            or when breaking down complex tasks into manageable pieces.
            
            Args:
                title: Plan name
                description: What this plan achieves (optional)
                steps: Comma-separated steps (optional - can add later)
            """
            try:
                step_list = []
                if steps:
                    step_list = [step.strip() for step in steps.split(",") if step.strip()]
                
                plan = Plan(
                    workspace_id=self.get_current_workspace(),
                    title=title,
                    description=description or f"Multi-step plan: {title}",
                    steps=step_list
                )
                
                if self.plan_storage.save(plan):
                    self.search_engine.index_plan(plan)
                    logger.info(f"Created plan {plan.id}")
                    
                    result = f"📋 **Plan Created: {title}**\\n\\n"
                    result += f"Description: {plan.description}\\n"
                    if step_list:
                        result += f"Steps ({len(step_list)}): {', '.join(step_list)}\\n"
                    result += f"\\nID: `{plan.id}`"
                    
                    return result
                else:
                    return "❌ Failed to create plan"
                    
            except Exception as e:
                logger.error(f"Error creating plan: {e}")
                return f"❌ Error creating plan: {e}"
        
        # 7. STANDUP - Quick status report  
        @mcp_server.tool
        async def standup() -> str:
            """Generate a quick standup report of your recent work.
            
            BEHAVIORAL GUIDANCE: Use for daily check-ins, progress reviews,
            or when user asks "what did I work on recently?"
            """
            try:
                return await self._generate_daily_standup()
            except Exception as e:
                logger.error(f"Error generating standup: {e}")
                return f"❌ Error generating standup: {e}"
    
    # Helper methods that implement the actual logic
    async def _recall_quick(self) -> str:
        """Quick recall implementation."""
        # Import here to avoid circular imports
        from .recall import RecallTool
        recall_tool = RecallTool(self.server)
        context = await recall_tool._build_recall_context(
            days_back=2, include_todos=True, include_plans=True, include_checkpoints=True
        )
        return self._format_optimized_recall(context)
    
    async def _recall_context(self, days_back: int) -> str:
        """Full recall implementation."""
        from .recall import RecallTool
        recall_tool = RecallTool(self.server)
        context = await recall_tool._build_recall_context(
            days_back=days_back, include_todos=True, include_plans=True, include_checkpoints=True
        )
        return self._format_optimized_recall(context)
    
    async def _recall_session(self, session_id: str) -> str:
        """Session recall implementation."""
        from .recall import RecallTool
        recall_tool = RecallTool(self.server)
        context = await recall_tool._build_recall_context(
            days_back=30, include_todos=True, include_plans=True, include_checkpoints=True,
            session_id=session_id
        )
        return self._format_optimized_recall(context)
    
    async def _recall_branch(self, git_branch: str) -> str:
        """Branch recall implementation."""
        from .recall import RecallTool
        recall_tool = RecallTool(self.server)
        context = await recall_tool._build_recall_context(
            days_back=14, include_todos=True, include_plans=True, include_checkpoints=True,
            git_branch=git_branch
        )
        return self._format_optimized_recall(context)
    
    def _format_optimized_recall(self, context: Dict) -> str:
        """Format recall context for optimal Claude Code display.
        
        Returns structured summary that avoids truncation while providing
        complete information in a format Claude can interpret and expand.
        """
        from ..models.todo import TodoStatus
        
        recall_time = context["recall_time"].strftime("%Y-%m-%d %H:%M")
        summary = context["summary"]
        
        # Core statistics
        result = f"🐘 **Tusk Memory Recall** - {recall_time}\\n"
        result += f"📁 **Workspace**: {context['workspace']}\\n\\n"
        
        # Summary with actionable counts
        result += f"📊 **Context Summary**\\n"
        result += f"- {summary['checkpoints_count']} checkpoints from last {summary['days_covered']} days\\n"
        result += f"- {summary['todos_count']} active todos ({summary['active_todos']} in progress, {summary['pending_todos']} pending)\\n"
        result += f"- {summary['plans_count']} active plans\\n\\n"
        
        if (summary["checkpoints_count"] == 0 and 
            summary["todos_count"] == 0 and 
            summary["plans_count"] == 0):
            result += "💭 **No recent context found** - This might be a fresh start!\\n"
            return result
        
        # Recent checkpoints (condensed)
        if context["checkpoints"]:
            result += f"## 📚 Recent Checkpoints ({len(context['checkpoints'])})\\n\\n"
            recent = sorted(context["checkpoints"], key=lambda c: c.created_at, reverse=True)[:3]
            
            for i, checkpoint in enumerate(recent, 1):
                created = checkpoint.created_at.strftime("%m-%d %H:%M")
                result += f"**{i}. [{created}] {checkpoint.description}**\\n"
                
                if checkpoint.highlights:
                    result += f"   💡 {len(checkpoint.highlights)} highlights\\n"
                
                if checkpoint.work_context:
                    preview = checkpoint.work_context[:80].replace('\\n', ' ')
                    result += f"   📝 {preview}...\\n"
                
                result += "\\n"
        
        # Active todos (grouped and summarized)
        if context["todos"]:
            result += f"## ✅ Active Todos ({len(context['todos'])})\\n\\n"
            
            in_progress = [t for t in context["todos"] if t.status == TodoStatus.IN_PROGRESS]
            pending = [t for t in context["todos"] if t.status == TodoStatus.PENDING]
            
            if in_progress:
                result += f"**🔄 In Progress ({len(in_progress)}):**\\n"
                for todo in in_progress[:2]:
                    result += f"- {todo.content}\\n"
                if len(in_progress) > 2:
                    result += f"- ... and {len(in_progress) - 2} more\\n"
                result += "\\n"
            
            if pending:
                result += f"**⏳ Pending ({len(pending)}):**\\n"
                for todo in pending[:3]:
                    result += f"- {todo.content}\\n"
                if len(pending) > 3:
                    result += f"- ... and {len(pending) - 3} more\\n"
                result += "\\n"
        
        # Active plans (concise)
        if context["plans"]:
            result += f"## 📋 Active Plans ({len(context['plans'])})\\n\\n"
            
            for plan in context["plans"][:2]:
                completed, total = plan.get_progress()
                result += f"**{plan.title}** ({completed}/{total})\\n"
                
                next_steps = plan.get_next_steps(1)
                if next_steps:
                    result += f"   🎯 Next: {next_steps[0].description[:60]}...\\n"
                result += "\\n"
        
        # Actionable next steps
        result += "## 🎯 Suggested Next Actions\\n\\n"
        
        if summary["active_todos"] > 0:
            result += "- Pick up in-progress todos\\n"
        if summary["pending_todos"] > 0:
            result += "- Start pending tasks\\n"
        if context["plans"]:
            result += "- Work on next plan steps\\n"
        
        result += "- Create checkpoint when you complete significant work\\n"
        result += "- Use search tool to find specific information\\n"
        
        return result
    
    async def _generate_daily_standup(self) -> str:
        """Daily standup implementation."""
        from .standup import StandupTool
        standup_tool = StandupTool(self.server)
        
        try:
            # Parse timeframe
            days_back = standup_tool._parse_timeframe("daily")
            
            # Build report data
            report_data = await standup_tool._build_standup_data(
                days_back=days_back,
                include_completed=True,
                include_plans=True,
                include_todos=True,
            )
            
            # Format and return report
            return standup_tool._format_standup_report(report_data, "daily")
            
        except Exception as e:
            return f"Γ¥î Error generating standup report: {e}"