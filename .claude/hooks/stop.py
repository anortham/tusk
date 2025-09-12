#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
Tusk Stop Hook - Auto-Completion Detection

Analyzes Claude's responses to detect when work is completed and suggests
marking todos/plans as completed. This helps prevent stale task buildup.

Key Features:
- Detects completion language patterns
- Suggests todo completion
- Tracks work completion patterns
- Non-blocking execution
"""

import argparse
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class CompletionDetector:
    """Detects work completion patterns in Claude's responses."""
    
    # Completion indicators
    COMPLETION_PATTERNS = [
        r'(?:task|work|feature|implementation|fix|bug)\s+(?:is\s+)?(?:complete|finished|done|implemented)',
        r'(?:successfully|fully)\s+(?:implemented|completed|finished|resolved)',
        r'(?:all\s+)?(?:tests?|changes?|features?)\s+(?:are\s+)?(?:working|complete|implemented)',
        r'(?:deployment|release|rollout)\s+(?:is\s+)?(?:complete|successful|finished)',
        r'(?:issue|problem|bug)\s+(?:is\s+)?(?:resolved|fixed|solved)',
        r'(?:ready for|prepared for|completed)\s+(?:review|testing|deployment|production)',
        r'(?:finished|completed|done with)\s+(?:the|this|that)\s+(?:feature|task|implementation)',
        r'(?:everything|all work)\s+(?:is\s+)?(?:complete|finished|ready)',
    ]
    
    # Todo-specific completion patterns
    TODO_COMPLETION_PATTERNS = [
        r'(?:todo|task)\s+(?:completed|finished|done)',
        r'(?:marked|set)\s+(?:todo|task)\s+as\s+(?:complete|done|finished)',
        r'(?:finished|completed)\s+(?:working on|implementing)\s+(.+)',
        r'(?:task|todo)\s+(.+?)\s+(?:is now|is\s+)?(?:complete|finished|done)',
    ]
    
    # Plan completion patterns
    PLAN_COMPLETION_PATTERNS = [
        r'(?:plan|project|milestone)\s+(?:is\s+)?(?:complete|finished|accomplished)',
        r'(?:all\s+)?(?:steps|phases|objectives)\s+(?:are\s+)?(?:complete|finished)',
        r'(?:project|implementation|plan)\s+(?:successfully\s+)?(?:completed|finished)',
        r'(?:reached|achieved|accomplished)\s+(?:the\s+)?(?:goal|objective|milestone)',
    ]
    
    def detect_completion(self, text: str) -> Dict[str, List[str]]:
        """Detect completion indicators in text."""
        results = {
            'general_completions': [],
            'todo_completions': [],
            'plan_completions': []
        }
        
        text_lower = text.lower()
        
        # General completion patterns
        for pattern in self.COMPLETION_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            if matches:
                # Extract context around matches
                full_matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in full_matches:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()
                    results['general_completions'].append(context)
        
        # Todo completion patterns
        for pattern in self.TODO_COMPLETION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                results['todo_completions'].append(context)
        
        # Plan completion patterns
        for pattern in self.PLAN_COMPLETION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()
                results['plan_completions'].append(context)
        
        return results
    
    def generate_completion_suggestions(self, completions: Dict[str, List[str]]) -> List[str]:
        """Generate actionable completion suggestions."""
        suggestions = []
        
        if completions['todo_completions']:
            suggestions.append("📝 Consider marking related todos as completed with `/todos complete <id>`")
        
        if completions['plan_completions']:
            suggestions.append("📋 Review active plans and mark completed steps/milestones")
        
        if completions['general_completions'] and not completions['todo_completions']:
            suggestions.append("🎯 Create a checkpoint to capture this completion: `/checkpoint \"<description>\"`")
        
        return suggestions


def main():
    try:
        # Parse command line arguments  
        parser = argparse.ArgumentParser(description="Tusk stop hook - completion detection")
        parser.add_argument('--detect-completion', action='store_true', default=True,
                          help='Detect work completion (default: True)')
        parser.add_argument('--suggest-actions', action='store_true', default=True,
                          help='Suggest completion actions (default: True)')
        parser.add_argument('--verbose', action='store_true',
                          help='Print verbose output')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Get the stop hook flag
        stop_hook_active = input_data.get('stop_hook_active', False)
        
        if not stop_hook_active:
            sys.exit(0)  # Not a stop event
        
        # We don't have access to Claude's response text directly in the hook,
        # but we can analyze any available context or transcript
        
        # Check for transcript file to analyze recent messages
        transcript_path = None
        session_id = input_data.get('session_id')
        
        if session_id:
            # Try common transcript locations
            potential_paths = [
                Path.home() / ".claude" / "transcripts" / f"{session_id}.jsonl",
                Path.cwd() / "transcripts" / f"{session_id}.jsonl", 
                Path.cwd() / f"{session_id}.jsonl",
            ]
            
            for path in potential_paths:
                if path.exists():
                    transcript_path = path
                    break
        
        if args.verbose:
            print(f"🔍 Analyzing completion patterns (session: {session_id[:8] if session_id else 'unknown'}...)")
        
        completion_detected = False
        suggestions = []
        
        if transcript_path and transcript_path.exists():
            try:
                # Read recent transcript entries
                recent_messages = []
                with open(transcript_path, 'r') as f:
                    lines = f.readlines()
                    # Get last few messages
                    for line in lines[-5:]:  # Last 5 messages
                        try:
                            msg = json.loads(line)
                            if msg.get('role') == 'assistant' and 'content' in msg:
                                recent_messages.append(msg['content'])
                        except json.JSONDecodeError:
                            continue
                
                # Analyze recent assistant messages for completion patterns
                if recent_messages:
                    detector = CompletionDetector()
                    
                    for message in recent_messages:
                        completions = detector.detect_completion(message)
                        
                        if any(completions.values()):
                            completion_detected = True
                            suggestions.extend(detector.generate_completion_suggestions(completions))
                            
                            if args.verbose:
                                total_completions = sum(len(v) for v in completions.values())
                                print(f"✅ Detected {total_completions} completion indicators")
                                break
            
            except Exception as e:
                if args.verbose:
                    print(f"⚠️ Could not analyze transcript: {e}")
        
        # Show suggestions if completion was detected
        if completion_detected and suggestions and args.suggest_actions:
            print("\\n🎉 **Work Completion Detected!**")
            print("\\nSuggested next actions:")
            for suggestion in suggestions[:3]:  # Limit to 3 suggestions
                print(f"- {suggestion}")
            print("\\nUse Tusk commands to keep your memory system up to date!")
        
        # Log the completion detection
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "stop_hook_completion_detection",
            "session_id": session_id,
            "completion_detected": completion_detected,
            "suggestions_count": len(suggestions),
            "transcript_analyzed": transcript_path is not None
        }
        
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
        
        # Keep only last 100 entries
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
        
        sys.exit(0)
        
    except json.JSONDecodeError:
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)  
    except Exception as e:
        if 'verbose' in locals() and args.verbose:
            print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == '__main__':
    main()