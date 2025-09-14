"""Test to expose PlanStep.status bug in enhanced_all.py

This test demonstrates the bug where enhanced_all.py tries to access
s.status on PlanStep objects, but PlanStep doesn't have a status attribute.
It has a completed boolean instead.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.tusk.models.plan import Plan, PlanStep


def test_buggy_code_directly():
    """
    Test the exact buggy code from enhanced_all.py line 318.

    This directly reproduces the bug without needing the full tool setup.
    """
    # Create a plan with completed steps - this mimics what would be in storage
    plan = Plan(
        title="Test Plan",
        description="A plan to test the bug"
    )

    # Add steps to the plan - some completed, some not
    completed_step = PlanStep(
        description="Completed step",
        completed=True  # This is the correct attribute name
    )
    pending_step = PlanStep(
        description="Pending step",
        completed=False
    )

    plan.steps = [completed_step, pending_step]

    # This is the exact buggy code from enhanced_all.py line 318:
    # "steps_completed": len([s for s in plan.steps if s.status == "completed"])

    # This should crash with "'PlanStep' object has no attribute 'status'"
    try:
        buggy_count = len([s for s in plan.steps if s.status == "completed"])
        # If we get here, the bug has been magically fixed somehow
        pytest.fail("Expected AttributeError for s.status, but it didn't happen!")
    except AttributeError as e:
        if "'PlanStep' object has no attribute 'status'" in str(e):
            print("✅ Successfully reproduced the bug!")
            print(f"Bug details: {e}")
        else:
            pytest.fail(f"Got different AttributeError than expected: {e}")

    # This is the CORRECT way to count completed steps:
    correct_count = len([s for s in plan.steps if s.completed])
    assert correct_count == 1

def test_buggy_code_from_line_508():
    """
    Test the second instance of the bug from enhanced_all.py line 508.
    """
    plan = Plan(title="Test Plan", description="Test")
    plan.steps = [
        PlanStep(description="Done", completed=True),
        PlanStep(description="Todo", completed=False),
        PlanStep(description="Also done", completed=True),
    ]

    # This is the buggy code from line 508:
    # completed_steps = len([s for s in plan.steps if s.status == "completed"])

    try:
        completed_steps = len([s for s in plan.steps if s.status == "completed"])
        pytest.fail("Expected AttributeError for s.status, but it didn't happen!")
    except AttributeError as e:
        if "'PlanStep' object has no attribute 'status'" in str(e):
            print("✅ Successfully reproduced the second bug instance!")
        else:
            pytest.fail(f"Got different AttributeError: {e}")

    # The correct way:
    correct_completed = len([s for s in plan.steps if s.completed])
    assert correct_completed == 2


def test_planstep_has_completed_not_status():
    """Verify that PlanStep model has 'completed' not 'status' attribute."""
    step = PlanStep(description="Test step")

    # PlanStep should have completed attribute
    assert hasattr(step, 'completed')
    assert isinstance(step.completed, bool)
    assert step.completed is False  # default value

    # PlanStep should NOT have status attribute
    assert not hasattr(step, 'status')

    # Verify we can mark it completed
    step.mark_completed()
    assert step.completed is True
    assert step.completed_at is not None


def test_plan_step_count_logic():
    """Test the correct logic for counting completed steps."""
    plan = Plan(
        title="Step Count Test",
        description="Testing step counting"
    )

    # Add mix of completed and pending steps
    steps = [
        PlanStep(description="Step 1", completed=True),
        PlanStep(description="Step 2", completed=False),
        PlanStep(description="Step 3", completed=True),
        PlanStep(description="Step 4", completed=False),
    ]

    plan.steps = steps

    # Test the correct way to count completed steps
    completed_count = len([s for s in plan.steps if s.completed])
    assert completed_count == 2

    # Test using the Plan model's built-in method
    completed, total = plan.get_progress()
    assert completed == 2
    assert total == 4
    assert plan.get_progress_percentage() == 50.0



if __name__ == "__main__":
    # Run the tests to see the bug in action
    try:
        test_buggy_code_directly()
        test_buggy_code_from_line_508()
        test_planstep_has_completed_not_status()
        test_plan_step_count_logic()
        print("🎉 All tests passed! The bugs are likely fixed.")
    except Exception as e:
        print(f"✅ Bug reproduced successfully: {e}")