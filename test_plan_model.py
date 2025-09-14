"""Focused tests for Plan model functionality.

Tests the core Plan model functionality to ensure step counting
and management work correctly after fixing the PlanStep.status bug.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.tusk.models.plan import Plan, PlanStep, PlanStatus


class TestPlanModel:
    """Test the Plan model's core functionality."""

    def test_plan_creation(self):
        """Test basic plan creation."""
        plan = Plan(
            title="Test Plan",
            description="A test plan for validation"
        )

        assert plan.title == "Test Plan"
        assert plan.description == "A test plan for validation"
        assert plan.status == PlanStatus.DRAFT  # Default status
        assert len(plan.steps) == 0
        assert plan.created_at is not None

    def test_plan_step_addition(self):
        """Test adding steps to a plan."""
        plan = Plan(title="Step Test", description="Testing step addition")

        # Add first step
        step1 = plan.add_step("First step", estimated_duration="1h")
        assert len(plan.steps) == 1
        assert step1.description == "First step"
        assert step1.estimated_duration == "1h"
        assert step1.completed is False
        assert step1.id is not None

        # Add second step with notes
        step2 = plan.add_step("Second step", notes="Important step")
        assert len(plan.steps) == 2
        assert step2.notes == "Important step"
        assert step2.completed is False

        # Verify plan was updated
        assert plan.updated_at is not None

    def test_step_completion(self):
        """Test completing individual steps."""
        plan = Plan(title="Completion Test", description="Testing step completion")

        step1 = plan.add_step("First step")
        step2 = plan.add_step("Second step")

        # Initially no steps are completed
        assert not step1.completed
        assert not step2.completed
        assert step1.completed_at is None

        # Complete first step
        success = plan.complete_step(step1.id)
        assert success is True
        assert step1.completed is True
        assert step1.completed_at is not None
        assert step2.completed is False  # Second step unchanged

        # Complete second step
        success = plan.complete_step(step2.id)
        assert success is True
        assert step2.completed is True

        # Try to complete non-existent step
        success = plan.complete_step("non-existent-id")
        assert success is False

    def test_progress_calculation(self):
        """Test progress calculation methods."""
        plan = Plan(title="Progress Test", description="Testing progress calculation")

        # Empty plan
        completed, total = plan.get_progress()
        assert completed == 0
        assert total == 0
        assert plan.get_progress_percentage() == 0.0
        assert plan.is_completed() is False

        # Add steps
        step1 = plan.add_step("Step 1")
        step2 = plan.add_step("Step 2")
        step3 = plan.add_step("Step 3")
        step4 = plan.add_step("Step 4")

        # No steps completed
        completed, total = plan.get_progress()
        assert completed == 0
        assert total == 4
        assert plan.get_progress_percentage() == 0.0
        assert plan.is_completed() is False

        # Complete some steps
        plan.complete_step(step1.id)
        plan.complete_step(step3.id)

        # Check progress
        completed, total = plan.get_progress()
        assert completed == 2
        assert total == 4
        assert plan.get_progress_percentage() == 50.0
        assert plan.is_completed() is False

        # Complete all steps
        plan.complete_step(step2.id)
        plan.complete_step(step4.id)

        # Check full completion
        completed, total = plan.get_progress()
        assert completed == 4
        assert total == 4
        assert plan.get_progress_percentage() == 100.0
        assert plan.is_completed() is True

    def test_next_actionable_steps(self):
        """Test getting next actionable steps."""
        plan = Plan(title="Next Steps Test", description="Testing next step logic")

        # Add steps with dependencies
        step1 = plan.add_step("Foundation step")
        step2 = plan.add_step("Dependent step", dependencies=[step1.id])
        step3 = plan.add_step("Independent step")  # No dependencies
        step4 = plan.add_step("Final step", dependencies=[step1.id, step2.id])

        # Initially, only steps without dependencies are actionable
        next_steps = plan.get_next_steps()
        next_step_ids = [step.id for step in next_steps]
        assert step1.id in next_step_ids
        assert step3.id in next_step_ids
        assert step2.id not in next_step_ids  # Has dependency
        assert step4.id not in next_step_ids  # Has dependencies

        # Complete foundation step
        plan.complete_step(step1.id)
        next_steps = plan.get_next_steps()
        next_step_ids = [step.id for step in next_steps]
        assert step1.id not in next_step_ids  # Already completed
        assert step2.id in next_step_ids  # Dependency satisfied
        assert step3.id in next_step_ids  # Still actionable
        assert step4.id not in next_step_ids  # Still has unsatisfied dependency

        # Complete dependent step
        plan.complete_step(step2.id)
        next_steps = plan.get_next_steps()
        next_step_ids = [step.id for step in next_steps]
        assert step4.id in next_step_ids  # All dependencies satisfied

        # Test limit parameter
        plan.add_step("Extra step 1")
        plan.add_step("Extra step 2")
        plan.add_step("Extra step 3")

        next_steps = plan.get_next_steps(limit=2)
        assert len(next_steps) <= 2

    def test_plan_status_transitions(self):
        """Test plan status transitions."""
        plan = Plan(title="Status Test", description="Testing status transitions")

        # Initial status
        assert plan.status == PlanStatus.DRAFT
        assert plan.started_at is None

        # Activate plan
        plan.activate()
        assert plan.status == PlanStatus.ACTIVE
        assert plan.started_at is not None
        assert plan.updated_at is not None

        # Complete plan
        plan.complete()
        assert plan.status == PlanStatus.COMPLETED
        assert plan.completed_at is not None

    def test_step_marking_methods(self):
        """Test step marking methods directly."""
        step = PlanStep(description="Test step")

        # Initial state
        assert step.completed is False
        assert step.completed_at is None

        # Mark completed
        step.mark_completed()
        assert step.completed is True
        assert step.completed_at is not None

    def test_plan_search_text_generation(self):
        """Test search text generation for plans."""
        plan = Plan(
            title="Authentication System",
            description="OAuth2 implementation with JWT tokens",
            priority="high",
            category="feature",
            goals=["Security", "OAuth2"],
            success_criteria=["Tests pass", "Security audit"],
            tags=["auth", "security"],
            notes="Critical for production"
        )

        # Add steps
        step1 = plan.add_step("Research providers", notes="Compare Auth0 vs Firebase")
        step2 = plan.add_step("Implement OAuth flow")

        # Generate search text
        search_text = plan.to_search_text()

        # Verify all relevant content is included
        assert "Authentication System" in search_text
        assert "OAuth2 implementation" in search_text
        assert "high" in search_text
        assert "feature" in search_text
        assert "Security" in search_text
        assert "OAuth2" in search_text
        assert "auth" in search_text
        assert "security" in search_text
        assert "Critical for production" in search_text
        assert "Research providers" in search_text
        assert "Compare Auth0 vs Firebase" in search_text
        assert "Implement OAuth flow" in search_text

    def test_critical_step_counting_logic(self):
        """
        Critical test: Verify the correct step counting logic that was buggy.

        This specifically tests the logic that was broken:
        len([s for s in plan.steps if s.status == "completed"])  # WRONG
        vs
        len([s for s in plan.steps if s.completed])  # CORRECT
        """
        plan = Plan(title="Step Counting Test", description="Critical step counting test")

        # Add mixed completion steps
        step1 = plan.add_step("Completed step 1")
        step2 = plan.add_step("Pending step 1")
        step3 = plan.add_step("Completed step 2")
        step4 = plan.add_step("Pending step 2")
        step5 = plan.add_step("Completed step 3")

        # Mark some as completed
        step1.mark_completed()
        step3.mark_completed()
        step5.mark_completed()

        # Test the CORRECT counting logic (what we fixed the bug to use)
        correct_count = len([s for s in plan.steps if s.completed])
        assert correct_count == 3

        # Test via Plan methods
        completed, total = plan.get_progress()
        assert completed == 3
        assert total == 5
        assert plan.get_progress_percentage() == 60.0

        # Test that the buggy logic would have failed (PlanStep has no status attribute)
        # This verifies our understanding of the bug
        try:
            # This should fail because PlanStep doesn't have 'status'
            buggy_count = len([s for s in plan.steps if s.status == "completed"])
            pytest.fail("Expected AttributeError for s.status")
        except AttributeError as e:
            assert "'PlanStep' object has no attribute 'status'" in str(e)

    def test_plan_string_representation(self):
        """Test plan string representation."""
        plan = Plan(title="String Test", description="Testing __str__ method")

        # Plan with no steps
        str_repr = str(plan)
        assert "DRAFT" in str_repr
        assert "String Test" in str_repr
        assert "(0/0)" in str_repr

        # Add steps
        step1 = plan.add_step("Step 1")
        step2 = plan.add_step("Step 2")
        plan.complete_step(step1.id)

        # Activate plan
        plan.activate()
        str_repr = str(plan)
        assert "ACTIVE" in str_repr
        assert "String Test" in str_repr
        assert "(1/2)" in str_repr  # 1 completed out of 2 total


if __name__ == "__main__":
    # Run a quick verification
    print("Running Plan model tests...")

    # Test critical step counting
    plan = Plan(title="Direct Test", description="Direct testing")
    step1 = plan.add_step("Done")
    step2 = plan.add_step("Todo")
    step3 = plan.add_step("Also done")

    plan.complete_step(step1.id)
    plan.complete_step(step3.id)

    # Verify correct counting
    correct_count = len([s for s in plan.steps if s.completed])
    progress_percentage = plan.get_progress_percentage()

    print(f"Completed steps: {correct_count}/3 = {progress_percentage}%")
    assert correct_count == 2
    assert progress_percentage == 66.66666666666666

    # Verify the bug would have occurred
    try:
        buggy_count = len([s for s in plan.steps if s.status == "completed"])
        print("ERROR: Expected AttributeError!")
    except AttributeError:
        print("✅ Confirmed: PlanStep has no 'status' attribute (as expected)")

    print("✅ Plan model tests completed successfully!")