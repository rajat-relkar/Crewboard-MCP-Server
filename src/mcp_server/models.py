"""Pydantic models and field types shared by the MCP tools and the database layer.

The ``Annotated`` aliases below are used directly in the tool signatures in
``server.py``. FastMCP turns them into the JSON schema that MCP clients (and
LLMs) see, and validates every incoming tool call against them before the
tool function runs.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints


def _normalize(value: object) -> object:
    """Trim and lowercase strings so inputs like "High" or " done " are accepted."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _normalize_status(value: object) -> object:
    value = _normalize(value)
    # Rows written by an earlier version of the server stored "to do".
    return "todo" if value == "to do" else value


Priority = Annotated[
    Literal["low", "medium", "high"],
    BeforeValidator(_normalize),
    Field(description="How important the task is"),
]

Status = Annotated[
    Literal["todo", "in progress", "done"],
    BeforeValidator(_normalize_status),
    Field(description="Where the task is in its lifecycle"),
]

TaskId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    Field(description="ID of the task, as returned by create_task or list_tasks"),
]

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    Field(description="Short name of the task"),
]

Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=2000),
    Field(description="Optional longer details about the task"),
]


class Task(BaseModel):
    """A task as stored in the database and returned by the tools."""

    task_id: TaskId
    title: Title
    description: Description = ""
    priority: Priority = "medium"
    status: Status = "todo"
    owner: str | None = Field(default=None, description="GitHub username of whoever created the task")


class TaskList(BaseModel):
    """Result of list_tasks.

    Returned as an object rather than a bare list because FastMCP sends an empty
    list as zero content blocks, which some LLM APIs (e.g. Groq) reject as an
    empty tool message.
    """

    count: int = Field(description="Number of tasks returned")
    tasks: list[Task]
