"""Tool enhancement utilities for rich parameter descriptions."""

import inspect
from collections.abc import Callable
from typing import Any

import docstring_parser
from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class ToolEnhancer:
    """Enhances FastMCP tools with rich parameter descriptions from docstrings."""

    @staticmethod
    def enhance_tool_parameters(func: Callable, existing_schema: dict[str, Any]) -> dict[str, Any]:
        """
        Enhance tool parameter schema with descriptions from docstring.

        Args:
            func: The function to analyze for docstring
            existing_schema: Existing parameter schema from FastMCP

        Returns:
            Enhanced schema with parameter descriptions
        """
        try:
            # Get the function's docstring
            docstring = inspect.getdoc(func)
            if not docstring:
                return existing_schema

            # Parse the docstring
            parsed_doc = docstring_parser.parse(docstring)
            if not parsed_doc.params:
                return existing_schema

            # Create parameter description mapping
            param_descriptions = {param.arg_name: param for param in parsed_doc.params}

            # Enhance the schema
            enhanced_schema = existing_schema.copy()
            if "properties" in enhanced_schema:
                for param_name, param_props in enhanced_schema["properties"].items():
                    if param_name in param_descriptions:
                        doc_param = param_descriptions[param_name]
                        if doc_param.description:
                            # Clean and format description
                            description = doc_param.description.strip().strip(".")
                            if description:
                                description = description[0].upper() + description[1:] + "."
                                param_props["description"] = description

            logger.debug(
                f"Enhanced tool {func.__name__} with {len(param_descriptions)} parameter descriptions"
            )
            return enhanced_schema

        except Exception as e:
            logger.warning(f"Failed to enhance tool {func.__name__}: {e}")
            return existing_schema

    @staticmethod
    def enhance_tool_description(func: Callable, existing_description: str) -> str:
        """
        Enhance tool description with return information from docstring.

        Args:
            func: The function to analyze for docstring
            existing_description: Existing description from FastMCP

        Returns:
            Enhanced description
        """
        try:
            # Get the function's docstring
            docstring = inspect.getdoc(func)
            if not docstring:
                return existing_description

            # Parse the docstring
            parsed_doc = docstring_parser.parse(docstring)

            # Start with existing description
            enhanced_description = existing_description.strip().strip(".")
            if enhanced_description:
                enhanced_description += "."

            # Add return description if available
            if parsed_doc.returns and parsed_doc.returns.description:
                return_desc = parsed_doc.returns.description.strip().strip(".")
                if return_desc:
                    prefix = " " if enhanced_description else ""
                    enhanced_description = f"{enhanced_description}{prefix}Returns {return_desc}."

            return enhanced_description

        except Exception as e:
            logger.warning(f"Failed to enhance description for {func.__name__}: {e}")
            return existing_description


def enhanced_tool(server_instance):
    """
    Decorator factory that creates an enhanced tool decorator.

    This works with FastMCP's @mcp_server.tool decorator to add rich parameter descriptions.

    Usage:
        @enhanced_tool(mcp_server)
        async def my_tool(param1: str, param2: int = 5) -> str:
            '''
            Tool description here.

            Args:
                param1: Description of first parameter with details and constraints
                param2: Description of second parameter with valid range 1-10

            Returns:
                Detailed description of what this returns
            '''
            return "result"
    """

    def decorator(func: Callable) -> Callable:
        # Get the original FastMCP tool decorator
        original_tool_decorator = server_instance.tool

        # Create enhanced version
        def enhanced_decorator(enhanced_func):
            # Apply the original FastMCP decorator first
            registered_func = original_tool_decorator(enhanced_func)

            # Now enhance the tool in the server's tool registry
            # This is a hook into FastMCP's internals - may need adjustment for different versions
            try:
                if hasattr(server_instance, "_tool_manager") and hasattr(
                    server_instance._tool_manager, "_tools"
                ):
                    tool_name = enhanced_func.__name__
                    if tool_name in server_instance._tool_manager._tools:
                        tool = server_instance._tool_manager._tools[tool_name]

                        # Enhance the parameter schema
                        if hasattr(tool, "parameters"):
                            tool.parameters = ToolEnhancer.enhance_tool_parameters(
                                enhanced_func, tool.parameters
                            )

                        # Enhance the description
                        if hasattr(tool, "description"):
                            tool.description = ToolEnhancer.enhance_tool_description(
                                enhanced_func, tool.description or ""
                            )

                        logger.info(f"Enhanced tool '{tool_name}' with rich parameter descriptions")

            except Exception as e:
                logger.error(f"Failed to enhance tool {enhanced_func.__name__}: {e}")

            return registered_func

        return enhanced_decorator(func)

    return decorator
