---
allowed-tools: mcp__tusk__recall, mcp__tusk__checkpoint, mcp__tusk__task, mcp__tusk__plan
description: Check for relevant context and optionally recall it
argument-hint: [auto|ask]
---

$if($1 == "ask")
**Context Check Mode:** Let me check what context is available and you can decide whether to recall it.

First, let me check for recent context using `recall(context="recent")`:

This will check recent checkpoints, tasks, and plans to see if there's relevant context for this session. 

If meaningful context exists, I'll summarize what's available and let you decide whether to do a full recall.

This prevents unwanted context loading while ensuring you don't miss important previous work.

$elif($1 == "auto")
**Auto-Recall Mode:** Automatically loading recent context using `recall(context="recent")`.

Checking for and loading relevant context from recent work sessions...

$else
**Smart Context Check:** 

Let me check if there's relevant context from recent sessions. I'll show you what's available and recommend whether to recall it.

This gives you control over context loading - useful when you want a fresh start vs continuing previous work.

Use `/recall-check ask` to review options first, or `/recall-check auto` to load context automatically.
$endif