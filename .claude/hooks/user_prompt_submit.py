#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
Tusk User Prompt Submit Hook

Captures plan mode discussions and other important context to prevent loss during compaction.
Automatically detects and saves plan refinements, technical decisions, and key discoveries.

Key Features:
- Detects plan mode discussions 
- Auto-saves plan updates and refinements
- Captures technical decisions and discoveries
- Creates checkpoints for significant discussions
- Non-blocking execution
"""

import argparse
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


class PlanModeDetector:
    """Detects and extracts plan-related information from user prompts."""
    
    # Patterns that indicate plan mode discussion
    PLAN_MODE_PATTERNS = [
        r'plan mode',
        r'planning',
        r'let.*plan',
        r'create.*plan',
        r'refine.*plan',
        r'update.*plan',
        r'step.*by.*step',
        r'implementation.*plan',
        r'roadmap',
        r'strategy',
        r'approach.*to',
    ]
    
    # Patterns for extracting plan details
    PLAN_DETAIL_PATTERNS = [
        r'(?:step|phase|stage)\s*\d+[:\-\s](.+)',
        r'(?:first|then|next|finally)[,\s]+(.+)',
        r'we.*(?:should|need to|will)\s+(.+)',
        r'implementation[:\s]+(.+)',
    ]
    
    # Decision indicators
    DECISION_PATTERNS = [
        r'(?:decided|decide|decision).*to\s+(.+)',
        r'(?:chose|choose|choice).*to\s+(.+)',
        r'(?:going with|will use|selected)\s+(.+)',
        r'the approach.*is\s+(.+)',
    ]
    
    # Discovery patterns
    DISCOVERY_PATTERNS = [
        r'(?:discovered|found|learned).*that\s+(.+)',
        r'(?:turns out|it seems).*that\s+(.+)',
        r'(?:realized|noticed)\s+(.+)',
        r'(?:interesting|important)[:\s]+(.+)',
    ]
    
    def is_plan_mode(self, prompt: str) -> bool:
        """Check if the prompt indicates plan mode discussion."""
        prompt_lower = prompt.lower()
        return any(re.search(pattern, prompt_lower) for pattern in self.PLAN_MODE_PATTERNS)
    
    def extract_plan_elements(self, prompt: str) -> Dict[str, List[str]]:
        """Extract plan elements from the prompt."""
        elements = {
            'steps': [],
            'decisions': [],
            'discoveries': [],
            'requirements': []
        }
        
        # Extract plan steps
        for pattern in self.PLAN_DETAIL_PATTERNS:
            matches = re.findall(pattern, prompt, re.IGNORECASE | re.MULTILINE)
            elements['steps'].extend([match.strip() for match in matches])
        
        # Extract decisions
        for pattern in self.DECISION_PATTERNS:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            elements['decisions'].extend([match.strip() for match in matches])
        
        # Extract discoveries
        for pattern in self.DISCOVERY_PATTERNS:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            elements['discoveries'].extend([match.strip() for match in matches])
        
        return elements


def save_plan_context(prompt: str, plan_elements: Dict[str, List[str]], session_id: str) -> bool:
    """Save plan context to Tusk."""
    try:
        import asyncio
        sys.path.insert(0, str(Path.cwd() / "src"))
        
        from tusk.server import TuskServer
        from tusk.config import TuskConfig
        from tusk.models.checkpoint import Checkpoint
        from tusk.models.highlight import Highlight, HighlightCategory
        
        async def save_context():
            config = TuskConfig.from_env()
            server = TuskServer(config)
            
            # Create a checkpoint with plan context
            description = "Plan mode discussion captured"
            
            checkpoint = Checkpoint(
                workspace_id="",
                description=description,
                work_context=f"Plan discussion context:\\n\\n{prompt[:500]}...",
                session_id=session_id,
            )
            
            # Add highlights for extracted elements
            highlights = []
            
            for step in plan_elements['steps'][:3]:  # Limit to first 3
                highlights.append(Highlight(
                    category=HighlightCategory.PLAN_STEP,
                    content=step,
                    context="Extracted from plan discussion"
                ))
            
            for decision in plan_elements['decisions'][:2]:  # Limit to first 2
                highlights.append(Highlight(
                    category=HighlightCategory.DECISION,
                    content=decision,
                    context="Decision made during planning"
                ))
            
            for discovery in plan_elements['discoveries'][:2]:  # Limit to first 2
                highlights.append(Highlight(
                    category=HighlightCategory.DISCOVERY,
                    content=discovery,
                    context="Discovery during plan discussion"
                ))
            
            checkpoint.highlights = highlights
            
            # Set TTL for plan checkpoints (7 days)
            checkpoint.set_ttl("7d")  # 7 days
            
            # Save checkpoint
            if server.checkpoint_storage.save(checkpoint):
                # Index for search
                server.search_engine.index_checkpoint(checkpoint)
                return True
            return False
        
        return asyncio.run(save_context())
        
    except Exception as e:
        print(f"Error saving plan context: {e}", file=sys.stderr)
        return False


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Tusk user prompt submit hook")
        parser.add_argument('--capture-plans', action='store_true', default=True,
                          help='Capture plan mode discussions (default: True)')
        parser.add_argument('--verbose', action='store_true',
                          help='Print verbose output')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract prompt and session info
        prompt = input_data.get('prompt', '')
        session_id = input_data.get('session_id', 'unknown')
        timestamp = input_data.get('timestamp', datetime.now(timezone.utc).isoformat())
        
        if not prompt:
            sys.exit(0)  # Nothing to process
        
        # Initialize detector
        detector = PlanModeDetector()
        
        # Check for plan mode
        is_plan_discussion = detector.is_plan_mode(prompt)
        
        if args.verbose and is_plan_discussion:
            try:
                print(f"🎯 Plan mode discussion detected (session: {session_id[:8]}...)")
            except UnicodeEncodeError:
                print(f"[PLAN] Plan mode discussion detected (session: {session_id[:8]}...)")
        
        # Process plan mode discussions
        if is_plan_discussion and args.capture_plans:
            if args.verbose:
                try:
                    print("📋 Extracting plan elements...")
                except UnicodeEncodeError:
                    print("[EXTRACT] Extracting plan elements...")
            
            plan_elements = detector.extract_plan_elements(prompt)
            
            # Only save if we extracted meaningful content
            has_content = any(len(elements) > 0 for elements in plan_elements.values())
            
            if has_content:
                if args.verbose:
                    try:
                        print(f"📝 Found {len(plan_elements['steps'])} steps, "
                              f"{len(plan_elements['decisions'])} decisions, "
                              f"{len(plan_elements['discoveries'])} discoveries")
                    except UnicodeEncodeError:
                        print(f"[FOUND] {len(plan_elements['steps'])} steps, "
                              f"{len(plan_elements['decisions'])} decisions, "
                              f"{len(plan_elements['discoveries'])} discoveries")
                
                success = save_plan_context(prompt, plan_elements, session_id)
                
                if args.verbose:
                    if success:
                        try:
                            print("✅ Plan context saved to checkpoint")
                        except UnicodeEncodeError:
                            print("[SUCCESS] Plan context saved to checkpoint")
                    else:
                        try:
                            print("❌ Failed to save plan context")
                        except UnicodeEncodeError:
                            print("[ERROR] Failed to save plan context")
        
        # Log the event
        log_dir = Path(".coa") / "tusk" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_entry = {
            "timestamp": timestamp,
            "event": "user_prompt_submit",
            "session_id": session_id,
            "prompt_length": len(prompt),
            "plan_mode_detected": is_plan_discussion,
            "context_saved": is_plan_discussion and has_content if is_plan_discussion else False
        }
        
        # Append to log file
        log_file = log_dir / 'tusk_hooks.json'
        if log_file.exists():
            with open(log_file, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        else:
            logs = []
        
        logs.append(log_entry)
        
        # Keep only last 100 entries to prevent log file growth
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
        
        # Success - return to continue processing
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        # Don't fail prompt processing due to hook errors
        sys.exit(0)


if __name__ == '__main__':
    main()