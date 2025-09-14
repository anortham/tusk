"""Test script to verify parameter enhancement is working."""

import asyncio
import inspect
import json
from src.tusk.tools.enhanced_simple import EnhancedUnifiedTaskTool
from src.tusk.config import TuskConfig
from src.tusk.storage import CheckpointStorage, PlanStorage, SearchEngine, TaskStorage
from fastmcp import FastMCP

class MockServer:
    """Mock server to test tool enhancement."""

    def __init__(self):
        config = TuskConfig.from_env()
        config.ensure_directories()

        self.config = config
        self.checkpoint_storage = CheckpointStorage(config)
        self.task_storage = TaskStorage(config)
        self.plan_storage = PlanStorage(config)
        self.search_engine = SearchEngine(config)

        # Create FastMCP instance
        self.mcp = FastMCP(name="TestTusk")

def test_enhancement():
    """Test if parameter descriptions are enhanced."""
    print("Testing parameter enhancement...")

    # Create mock server
    server = MockServer()

    # Create enhanced tool
    enhanced_task = EnhancedUnifiedTaskTool(server)

    # Register the tool
    enhanced_task.register(server.mcp)

    # Check if tool was registered
    if hasattr(server.mcp, '_tool_manager') and hasattr(server.mcp._tool_manager, '_tools'):
        tools = server.mcp._tool_manager._tools
        if 'task' in tools:
            tool = tools['task']
            print(f"[OK] Todo tool found: {tool}")

            # Check parameters schema
            if hasattr(tool, 'parameters'):
                params = tool.parameters
                print(f"\n[PARAMS] Parameter Schema:")
                print(json.dumps(params, indent=2))

                # Check if parameter descriptions were injected
                if 'properties' in params:
                    for param_name, param_info in params['properties'].items():
                        if 'description' in param_info:
                            print(f"\n[OK] Parameter '{param_name}' has description:")
                            print(f"   {param_info['description']}")
                        else:
                            print(f"\n[ERROR] Parameter '{param_name}' missing description")
                else:
                    print("\n[ERROR] No properties found in parameter schema")
            else:
                print("\n[ERROR] Tool has no parameters attribute")

            # Check tool description
            if hasattr(tool, 'description'):
                print(f"\n[DESC] Tool Description:")
                print(f"   {tool.description}")
            else:
                print("\n[ERROR] Tool has no description")
        else:
            print("[ERROR] Todo tool not found in registry")
            print(f"Available tools: {list(tools.keys())}")
    else:
        print("[ERROR] FastMCP tool manager not accessible")

if __name__ == "__main__":
    test_enhancement()