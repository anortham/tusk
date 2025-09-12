"""Plan tools for persistent multi-step project management."""

import logging
from typing import List, Optional

from ..models.plan import Plan, PlanStatus, PlanStep
from .base import BaseTool

logger = logging.getLogger(__name__)


class PlanTool(BaseTool):
    """Tools for managing persistent plans and projects."""
    
    def register(self, mcp_server) -> None:
        """Register plan tools with the MCP server."""
        
        @mcp_server.tool
        async def create_plan(
            title: str,
            description: str,
            steps: Optional[List[str]] = None,
        ) -> str:
            """Create a new plan for multi-step projects.
            
            Args:
                title: Plan title
                description: Detailed description of what this plan achieves
                steps: Initial list of steps (more can be added later)
            """
            try:
                plan = Plan(
                    workspace_id=self.get_current_workspace(),
                    title=title,
                    description=description,
                    goals=[],
                    priority="medium",
                    tags=[],
                )
                
                # Add initial steps if provided
                if steps:
                    for step_desc in steps:
                        plan.add_step(step_desc)
                
                if self.plan_storage.save(plan):
                    # Index for search
                    self.search_engine.index_plan(plan)
                    
                    logger.info(f"Created plan {plan.id}")
                    
                    result = f"📋 **Plan Created Successfully**\\n\\n"
                    result += f"**Title**: {title}\\n"
                    result += f"**ID**: `{plan.id}`\\n"
                    
                    if steps:
                        result += f"**Initial Steps**: {len(steps)}\\n"
                    
                    result += f"\\n💡 Use 'activate_plan {plan.id}' to start working on it!"
                    
                    return result
                else:
                    return "❌ Failed to create plan"
                    
            except Exception as e:
                logger.error(f"Error creating plan: {e}")
                return f"❌ Error creating plan: {e}"
        
        @mcp_server.tool
        async def list_plans(limit: int = 10) -> str:
            """List recent plans."""
            try:
                plans = self.plan_storage.find_recent(limit)
                
                if not plans:
                    return "No plans found."
                
                result = f"📋 **Plans** ({len(plans)} items)\\n\\n"
                
                for i, plan in enumerate(plans, 1):
                    completed, total = plan.get_progress()
                    progress_pct = plan.get_progress_percentage()
                    
                    # Status icon
                    status_icons = {
                        PlanStatus.DRAFT: "📝",
                        PlanStatus.ACTIVE: "🚀",
                        PlanStatus.ON_HOLD: "⏸️",
                        PlanStatus.COMPLETED: "✅",
                        PlanStatus.CANCELLED: "❌",
                    }
                    icon = status_icons.get(plan.status, "❓")
                    
                    result += f"**{i}. {icon} {plan.title}**\\n"
                    result += f"   ID: `{plan.id}` | Status: {plan.status.value}\\n"
                    result += f"   Progress: {completed}/{total} ({progress_pct:.0f}%)\\n\\n"
                
                return result
                
            except Exception as e:
                logger.error(f"Error listing plans: {e}")
                return f"❌ Error listing plans: {e}"
        
        @mcp_server.tool
        async def activate_plan(plan_id: str) -> str:
            """Activate a plan to start working on it."""
            try:
                plan = self.plan_storage.load(plan_id)
                if not plan:
                    return f"❌ Plan {plan_id} not found"
                
                if plan.status == PlanStatus.ACTIVE:
                    return f"✋ Plan '{plan.title}' is already active"
                
                plan.activate()
                
                if self.plan_storage.save(plan):
                    # Update search index
                    self.search_engine.index_plan(plan)
                    
                    result = f"🚀 **Activated Plan**: {plan.title}\\n\\n"
                    
                    # Show next steps
                    next_steps = plan.get_next_steps(3)
                    if next_steps:
                        result += "🎯 **Next Steps**:\\n"
                        for i, step in enumerate(next_steps, 1):
                            result += f"{i}. {step.description}\\n"
                    else:
                        result += "💡 Add steps to this plan to get started!"
                    
                    return result
                else:
                    return "❌ Failed to activate plan"
                    
            except Exception as e:
                logger.error(f"Error activating plan: {e}")
                return f"❌ Error activating plan: {e}"
        
        @mcp_server.tool
        async def complete_step(plan_id: str, step_number: int) -> str:
            """Mark a step in a plan as completed.
            
            Args:
                plan_id: ID of the plan
                step_number: Step number (1-based) to complete
            """
            try:
                plan = self.plan_storage.load(plan_id)
                if not plan:
                    return f"❌ Plan {plan_id} not found"
                
                if step_number < 1 or step_number > len(plan.steps):
                    return f"❌ Invalid step number. Plan has {len(plan.steps)} steps."
                
                step = plan.steps[step_number - 1]
                
                if step.completed:
                    return f"✅ Step {step_number} already completed: {step.description}"
                
                step.mark_completed()
                
                if self.plan_storage.save(plan):
                    # Update search index
                    self.search_engine.index_plan(plan)
                    
                    # Check if plan is now complete
                    if plan.is_completed() and plan.status != PlanStatus.COMPLETED:
                        plan.complete()
                        self.plan_storage.save(plan)
                        self.search_engine.index_plan(plan)
                    
                    completed, total = plan.get_progress()
                    progress_pct = plan.get_progress_percentage()
                    
                    result = f"✅ **Step Completed**\\n\\n"
                    result += f"**Plan**: {plan.title}\\n"
                    result += f"**Step {step_number}**: {step.description}\\n"
                    result += f"**Progress**: {completed}/{total} ({progress_pct:.0f}%)\\n\\n"
                    
                    if plan.status == PlanStatus.COMPLETED:
                        result += "🎉 **Plan Complete!** All steps are done.\\n"
                    else:
                        # Show next steps
                        next_steps = plan.get_next_steps(2)
                        if next_steps:
                            result += "🎯 **Next Steps**:\\n"
                            for next_step in next_steps:
                                step_idx = plan.steps.index(next_step) + 1
                                result += f"- Step {step_idx}: {next_step.description}\\n"
                    
                    return result
                else:
                    return "❌ Failed to update plan"
                    
            except Exception as e:
                logger.error(f"Error completing step: {e}")
                return f"❌ Error completing step: {e}"