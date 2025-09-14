"""Storage for plan data."""

import logging

from ..models.plan import Plan, PlanStatus
from .base import BaseStorage

logger = logging.getLogger(__name__)


class PlanStorage(BaseStorage[Plan]):
    """Storage for plans."""

    def __init__(self, config):
        super().__init__(config, Plan)

    def get_storage_subdir(self) -> str:
        return "plans"

    def find_by_status(self, status: PlanStatus) -> list[Plan]:
        """Find plans by status."""
        all_plans = self.load_all()
        return [plan for plan in all_plans if plan.status == status]

    def find_active(self) -> list[Plan]:
        """Find all active plans."""
        return self.find_by_status(PlanStatus.ACTIVE)

    def find_draft(self) -> list[Plan]:
        """Find all draft plans."""
        return self.find_by_status(PlanStatus.DRAFT)

    def find_completed(self) -> list[Plan]:
        """Find all completed plans."""
        return self.find_by_status(PlanStatus.COMPLETED)

    def find_by_tags(self, tags: list[str]) -> list[Plan]:
        """Find plans that have any of the specified tags."""
        all_plans = self.load_all()
        matching_plans = []

        for plan in all_plans:
            if any(tag in plan.tags for tag in tags):
                matching_plans.append(plan)

        # Sort by updated_at, most recent first
        matching_plans.sort(key=lambda p: p.updated_at or p.created_at, reverse=True)
        return matching_plans

    def find_by_category(self, category: str) -> list[Plan]:
        """Find plans by category."""
        all_plans = self.load_all()
        return [plan for plan in all_plans if plan.category == category]

    def find_recent(self, limit: int = 10) -> list[Plan]:
        """Find most recently updated plans."""
        all_plans = self.load_all()
        all_plans.sort(key=lambda p: p.updated_at or p.created_at, reverse=True)
        return all_plans[:limit]

    def get_plans_with_todos(self) -> list[Plan]:
        """Get plans that have associated todos."""
        all_plans = self.load_all()
        return [plan for plan in all_plans if plan.related_todo_ids]

    def get_plans_with_checkpoints(self) -> list[Plan]:
        """Get plans that have associated checkpoints."""
        all_plans = self.load_all()
        return [plan for plan in all_plans if plan.related_checkpoint_ids]

    def get_summary_stats(self) -> dict:
        """Get summary statistics about plans."""
        all_plans = self.load_all()

        stats = {
            "total": len(all_plans),
            "draft": 0,
            "active": 0,
            "on_hold": 0,
            "completed": 0,
            "cancelled": 0,
            "total_steps": 0,
            "completed_steps": 0,
        }

        for plan in all_plans:
            stats[plan.status.value] = stats.get(plan.status.value, 0) + 1
            stats["total_steps"] += len(plan.steps)
            stats["completed_steps"] += sum(1 for step in plan.steps if step.completed)

        # Calculate overall progress percentage
        if stats["total_steps"] > 0:
            stats["progress_percentage"] = (stats["completed_steps"] / stats["total_steps"]) * 100
        else:
            stats["progress_percentage"] = 0.0

        return stats

    def auto_complete_plans(self) -> list[str]:
        """Auto-complete plans where all steps are done. Returns list of completed plan IDs."""
        completed_plan_ids = []

        for plan in self.load_all():
            if plan.status != PlanStatus.COMPLETED and plan.is_completed():
                plan.complete()
                if self.save(plan):
                    completed_plan_ids.append(plan.id)
                    logger.info(f"Auto-completed plan {plan.id}: {plan.title}")

        return completed_plan_ids

    def get_next_actionable_steps(self, limit: int = 10) -> list[tuple[Plan, list]]:
        """Get next actionable steps from all active plans."""
        active_plans = self.find_active()
        plan_steps = []

        for plan in active_plans:
            next_steps = plan.get_next_steps(limit)
            if next_steps:
                plan_steps.append((plan, next_steps))

        return plan_steps

    def search_by_content(self, query: str) -> list[Plan]:
        """Simple text search across plan titles and descriptions."""
        query_lower = query.lower()
        all_plans = self.load_all()
        matching_plans = []

        for plan in all_plans:
            # Search in title, description, goals, and step descriptions
            searchable_text = " ".join(
                [
                    plan.title,
                    plan.description,
                    " ".join(plan.goals),
                    " ".join(step.description for step in plan.steps),
                ]
            ).lower()

            if query_lower in searchable_text:
                matching_plans.append(plan)

        # Sort by relevance (simple: title matches first, then description)
        def relevance_score(plan):
            score = 0
            if query_lower in plan.title.lower():
                score += 10
            if query_lower in plan.description.lower():
                score += 5
            return score

        matching_plans.sort(key=relevance_score, reverse=True)
        return matching_plans
