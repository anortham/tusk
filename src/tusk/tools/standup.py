"""Standup tool for work summaries and progress reports."""

from datetime import timezone
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .base import BaseTool

logger = logging.getLogger(__name__)


class StandupTool(BaseTool):
    """Tool for generating standup reports and work summaries."""
    
    def register(self, mcp_server) -> None:
        """Register standup tools with the MCP server."""
        
        @mcp_server.tool
        async def standup(
            timeframe: str = "daily",
            include_completed: bool = True,
            include_plans: bool = True,
            include_todos: bool = True,
        ) -> str:
            """📊 Generate a standup report of your recent work.
            
            Perfect for daily standups, weekly reviews, or progress check-ins.
            
            Args:
                timeframe: Report timeframe (daily/yesterday/weekly/monthly)
                include_completed: Include completed items
                include_plans: Include plan progress
                include_todos: Include todo status
            """
            try:
                # Parse timeframe
                days_back = self._parse_timeframe(timeframe)
                
                # Build report data
                report_data = await self._build_standup_data(
                    days_back=days_back,
                    include_completed=include_completed,
                    include_plans=include_plans,
                    include_todos=include_todos,
                )
                
                # Return structured data instead of formatted text
                return self._build_standup_response(report_data, timeframe)
                
            except Exception as e:
                logger.error(f"Error generating standup: {e}")
                return {"error": f"Error generating standup report: {e}", "success": False}
        
        @mcp_server.tool
        async def daily_standup() -> str:
            """📅 Quick daily standup - what you worked on yesterday and today's plan."""
            return await standup(timeframe="daily", include_completed=True)
        
        @mcp_server.tool
        async def weekly_standup() -> str:
            """📅 Weekly standup - comprehensive review of the past week."""
            return await standup(timeframe="weekly", include_completed=True)
        
        @mcp_server.tool
        async def work_summary(days_back: int = 3) -> str:
            """📋 Get a summary of work done in the last N days.
            
            Args:
                days_back: Number of days to look back
            """
            try:
                report_data = await self._build_standup_data(
                    days_back=days_back,
                    include_completed=True,
                    include_plans=True,
                    include_todos=True,
                )
                
                return self._format_work_summary(report_data, days_back)
                
            except Exception as e:
                logger.error(f"Error generating work summary: {e}")
                return f"❌ Error generating work summary: {e}"
    
    def _parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string into days back."""
        timeframe_map = {
            "daily": 1,
            "yesterday": 1,
            "weekly": 7,
            "monthly": 30,
            "week": 7,
            "month": 30,
        }
        
        return timeframe_map.get(timeframe.lower(), 1)
    
    async def _build_standup_data(
        self,
        days_back: int,
        include_completed: bool,
        include_plans: bool,
        include_todos: bool,
    ) -> Dict:
        """Build the data for standup report."""
        
        # Calculate time range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        data = {
            "workspace": self.get_current_workspace(),
            "timeframe": {
                "start": start_date,
                "end": end_date,
                "days": days_back,
            },
            "checkpoints": [],
            "todos": {
                "completed": [],
                "active": [],
                "created": [],
            },
            "plans": {
                "active": [],
                "completed_steps": [],
                "progress": {},
            },
            "stats": {},
        }
        
        # Get checkpoints from timeframe
        data["checkpoints"] = self.checkpoint_storage.list_by_date_range(start_date, end_date)
        
        # Get todos
        if include_todos:
            all_todos = self.todo_storage.load_all()
            
            for todo in all_todos:
                # Created in timeframe
                if todo.created_at >= start_date:
                    data["todos"]["created"].append(todo)
                
                # Completed in timeframe
                if (include_completed and 
                    todo.completed_at and 
                    todo.completed_at >= start_date):
                    data["todos"]["completed"].append(todo)
                
                # Currently active
                if todo.status.value in ["pending", "in_progress"]:
                    data["todos"]["active"].append(todo)
        
        # Get plans
        if include_plans:
            active_plans = self.plan_storage.find_active()
            all_plans = self.plan_storage.load_all()
            
            for plan in all_plans:
                # Active plans
                if plan in active_plans:
                    data["plans"]["active"].append(plan)
                    data["plans"]["progress"][plan.id] = plan.get_progress()
                
                # Steps completed in timeframe
                for step in plan.steps:
                    if (step.completed_at and 
                        step.completed_at >= start_date):
                        data["plans"]["completed_steps"].append((plan, step))
        
        # Calculate stats
        data["stats"] = {
            "checkpoints_created": len(data["checkpoints"]),
            "todos_created": len(data["todos"]["created"]),
            "todos_completed": len(data["todos"]["completed"]),
            "active_todos": len(data["todos"]["active"]),
            "active_plans": len(data["plans"]["active"]),
            "steps_completed": len(data["plans"]["completed_steps"]),
        }
        
        return data
    
    def _build_standup_response(self, data: Dict, timeframe: str) -> str:
        """Build structured standup response as JSON."""
        
        # Convert datetime objects to ISO strings for JSON serialization
        def serialize_datetime(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return str(obj)
        
        # Build structured response
        response = {
            "success": True,
            "timeframe": timeframe,
            "workspace": data["workspace"],
            "period_days": data["timeframe"]["days"],
            "stats": data["stats"],
            "completed": [],
            "in_progress": [],
            "planned": [],
            "blockers": []
        }
        
        # Add completed work
        for checkpoint in data["checkpoints"]:
            response["completed"].append({
                "type": "checkpoint",
                "time": serialize_datetime(checkpoint.created_at),
                "description": checkpoint.description,
                "highlights": [h.content[:100] for h in (checkpoint.highlights or [])][:2]
            })
        
        for todo in data["todos"]["completed"]:
            response["completed"].append({
                "type": "todo",
                "time": serialize_datetime(todo.completed_at),
                "description": todo.content
            })
        
        for plan, step in data["plans"]["completed_steps"]:
            response["completed"].append({
                "type": "plan_step",
                "time": serialize_datetime(step.completed_at),
                "description": f"{plan.title}: {step.description}"
            })
        
        # Add in-progress work
        active_todos = data["todos"]["active"]
        in_progress = [t for t in active_todos if t.status.value == "in_progress"]
        for todo in in_progress:
            response["in_progress"].append({
                "type": "todo",
                "description": todo.content,
                "status": todo.status.value
            })
        
        # Add planned work (pending todos)
        pending = [t for t in active_todos if t.status.value == "pending"]
        for todo in pending[:5]:  # Limit to top 5
            response["planned"].append({
                "type": "todo", 
                "description": todo.content
            })
        
        # Add active plans
        for plan in data["plans"]["active"]:
            completed, total = data["plans"]["progress"][plan.id]
            progress_pct = (completed / total * 100) if total > 0 else 0
            next_steps = plan.get_next_steps(1)
            
            response["in_progress"].append({
                "type": "plan",
                "title": plan.title,
                "progress": f"{completed}/{total} ({progress_pct:.0f}%)",
                "next_step": next_steps[0].description if next_steps else None
            })
        
        # Add blockers
        blocked_todos = [t for t in active_todos if t.status.value == "blocked"]
        for todo in blocked_todos:
            blocker_reason = None
            if todo.notes and "blocked:" in todo.notes.lower():
                lines = todo.notes.split('\n')
                for line in lines:
                    if line.lower().startswith('blocked:'):
                        blocker_reason = line
                        break
            
            response["blockers"].append({
                "type": "todo",
                "description": todo.content,
                "reason": blocker_reason
            })
        
        # Return as JSON string
        return json.dumps(response, indent=2)
    
    def _format_standup_report(self, data: Dict, timeframe: str) -> str:
        """Format standup report output."""
        
        workspace = data["workspace"]
        stats = data["stats"]
        timeframe_days = data["timeframe"]["days"]
        
        # Header
        report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = f"📊 **{timeframe.title()} Standup Report** - {report_date}\\n"
        result += f"📁 **Workspace**: {workspace}\\n\\n"
        
        # Quick stats
        result += f"## 📈 Quick Stats ({timeframe_days} days)\\n"
        result += f"- 📚 Checkpoints created: {stats['checkpoints_created']}\\n"
        result += f"- ✅ Todos completed: {stats['todos_completed']}\\n"
        result += f"- 📝 New todos: {stats['todos_created']}\\n"
        result += f"- 🚀 Active plans: {stats['active_plans']}\\n"
        result += f"- 🎯 Steps completed: {stats['steps_completed']}\\n\\n"
        
        # What I worked on (checkpoints and completed todos)
        result += f"## 🔨 What I Worked On\\n\\n"
        
        # Recent checkpoints
        if data["checkpoints"]:
            result += f"**📚 Recent Checkpoints ({len(data['checkpoints'])}):**\\n"
            for checkpoint in data["checkpoints"][:5]:  # Limit for readability
                created = checkpoint.created_at.strftime("%m-%d %H:%M")
                result += f"- [{created}] {checkpoint.description}\\n"
                
                # Show key highlights
                if checkpoint.highlights:
                    for highlight in checkpoint.highlights[:2]:
                        result += f"  💡 {highlight.content[:60]}...\\n"
            result += "\\n"
        
        # Completed todos
        if data["todos"]["completed"]:
            result += f"**✅ Completed Todos ({len(data['todos']['completed'])}):**\\n"
            for todo in data["todos"]["completed"]:
                completed = todo.completed_at.strftime("%m-%d %H:%M")
                result += f"- [{completed}] {todo.content}\\n"
            result += "\\n"
        
        # Completed plan steps
        if data["plans"]["completed_steps"]:
            result += f"**🎯 Plan Steps Completed ({len(data['plans']['completed_steps'])}):**\\n"
            for plan, step in data["plans"]["completed_steps"]:
                completed = step.completed_at.strftime("%m-%d %H:%M")
                result += f"- [{completed}] {plan.title}: {step.description}\\n"
            result += "\\n"
        
        # What I'm working on (active items)
        result += f"## 🚀 What I'm Working On\\n\\n"
        
        # Active todos
        if data["todos"]["active"]:
            in_progress = [t for t in data["todos"]["active"] if t.status.value == "in_progress"]
            pending = [t for t in data["todos"]["active"] if t.status.value == "pending"]
            
            if in_progress:
                result += f"**🔄 In Progress ({len(in_progress)}):**\\n"
                for todo in in_progress:
                    result += f"- {todo.get_display_form()}\\n"
                result += "\\n"
            
            if pending:
                result += f"**⏳ Coming Up ({len(pending[:3])}):**\\n"  # Show top 3
                for todo in pending[:3]:
                    result += f"- {todo.content}\\n"
                if len(pending) > 3:
                    result += f"- ... and {len(pending) - 3} more\\n"
                result += "\\n"
        
        # Active plans progress
        if data["plans"]["active"]:
            result += f"**📋 Active Plans ({len(data['plans']['active'])}):**\\n"
            for plan in data["plans"]["active"]:
                completed, total = data["plans"]["progress"][plan.id]
                progress_pct = (completed / total * 100) if total > 0 else 0
                
                result += f"- **{plan.title}** ({completed}/{total} - {progress_pct:.0f}%)\\n"
                
                # Show next step
                next_steps = plan.get_next_steps(1)
                if next_steps:
                    result += f"  🎯 Next: {next_steps[0].description}\\n"
                
            result += "\\n"
        
        # Blockers or issues
        blocked_todos = [t for t in data["todos"]["active"] if t.status.value == "blocked"]
        if blocked_todos:
            result += f"## 🚫 Blockers\\n\\n"
            for todo in blocked_todos:
                result += f"- {todo.content}\\n"
                if todo.notes and "blocked:" in todo.notes.lower():
                    # Extract blocker reason
                    lines = todo.notes.split('\\n')
                    for line in lines:
                        if line.lower().startswith('blocked:'):
                            result += f"  *{line}*\\n"
                            break
            result += "\\n"
        
        # If nothing to report
        if (not data["checkpoints"] and 
            not data["todos"]["completed"] and 
            not data["todos"]["active"] and 
            not data["plans"]["active"]):
            result += "💭 **Quiet period** - No significant activity in the timeframe.\\n"
            result += "Consider creating a checkpoint or todo to track your work!\\n"
        
        return result
    
    def _format_work_summary(self, data: Dict, days_back: int) -> str:
        """Format work summary output (more concise than standup)."""
        
        workspace = data["workspace"]
        stats = data["stats"]
        
        result = f"📋 **Work Summary** - Last {days_back} Days\\n"
        result += f"📁 Workspace: {workspace}\\n\\n"
        
        # Activity overview
        total_activity = (stats["checkpoints_created"] + 
                         stats["todos_completed"] + 
                         stats["steps_completed"])
        
        if total_activity == 0:
            result += "💭 No recorded activity in this timeframe.\\n"
            return result
        
        result += f"**Activity Overview:**\\n"
        result += f"- 📚 {stats['checkpoints_created']} checkpoints saved\\n"
        result += f"- ✅ {stats['todos_completed']} todos completed\\n"
        result += f"- 🎯 {stats['steps_completed']} plan steps finished\\n\\n"
        
        # Key accomplishments
        accomplishments = []
        
        # Add checkpoint descriptions
        for checkpoint in data["checkpoints"]:
            accomplishments.append(f"📚 {checkpoint.description}")
        
        # Add completed todos
        for todo in data["todos"]["completed"]:
            accomplishments.append(f"✅ {todo.content}")
        
        # Add completed steps
        for plan, step in data["plans"]["completed_steps"]:
            accomplishments.append(f"🎯 {plan.title}: {step.description}")
        
        if accomplishments:
            result += f"**Key Accomplishments:**\\n"
            for item in accomplishments[:10]:  # Limit for readability
                result += f"- {item}\\n"
            
            if len(accomplishments) > 10:
                result += f"- ... and {len(accomplishments) - 10} more items\\n"
        
        return result