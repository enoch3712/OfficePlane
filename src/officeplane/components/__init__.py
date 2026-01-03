"""
OfficePlane Component Framework

A component framework for office document operations, inspired by CrewAI Agents.
Supports both tool-provider mode (expose as function-call/MCP tools) and
self-executing mode (kickoff with a tool-calling LLM).
"""

from officeplane.components.context import ComponentContext
from officeplane.components.memory import ComponentMemory, InMemoryComponentMemory
from officeplane.components.action import ComponentAction
from officeplane.components.base import OfficeComponent
from officeplane.components.doc import DocComponent
from officeplane.components.author import AuthorComponent

__all__ = [
    "ComponentContext",
    "ComponentMemory",
    "InMemoryComponentMemory",
    "ComponentAction",
    "OfficeComponent",
    "DocComponent",
    "AuthorComponent",
]
