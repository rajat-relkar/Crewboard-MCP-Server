import os
from uuid import uuid4

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.dependencies import get_access_token

from mcp_server.database import (
    get_all_tasks,
    get_task,
    init_db,
    save_task,
    update_task_status_in_db
)
from mcp_server.models import Description, Priority, Status, Task, TaskId, TaskList, Title

load_dotenv()

PORT = 8083

try:
    github_client_id = os.environ["GITHUB_CLIENT_ID"]
    github_client_secret = os.environ["GITHUB_CLIENT_SECRET"]
except KeyError as missing:
    raise SystemExit(f"{missing} is not set. Add it to the .env file (see .env.example).")

# Users log in with GitHub. FastMCP handles the OAuth 2.0 flow and the discovery
# endpoints MCP clients look for, and rejects requests without a valid token.
# The GitHub OAuth app's callback URL must be http://127.0.0.1:8083/auth/callback
auth = GitHubProvider(
    client_id=github_client_id,
    client_secret=github_client_secret,
    base_url=f"http://127.0.0.1:{PORT}",
)

mcp = FastMCP("MCP SERVER RR", auth=auth)


def current_user() -> str:
    """Return the GitHub username of whoever is calling the tool."""
    token = get_access_token()
    login = token.claims.get("login") if token else None
    if not login:
        raise ToolError("You must be logged in with GitHub to use this tool")
    return login


@mcp.tool(name="create_task", description="This tool is used to create new tasks")
def create_task(title: Title, priority: Priority = "medium", description: Description = "") -> Task:
    """
    This function creates new tasks in our database
    """
    task = Task(
        task_id=str(uuid4()),
        title=title,
        description=description,
        priority=priority,
        owner=current_user(),
    )

    save_task(task)

    return task

@mcp.tool(name="list_tasks", description="This tool provides the list of all tasks in our database, from every user, with each task's owner")
def list_tasks() -> TaskList:
    """
    This function return all the tasks in our database, from every user
    """

    current_user()  # any logged-in user may see every task
    tasks = get_all_tasks()
    return TaskList(count=len(tasks), tasks=tasks)


@mcp.tool(name="update_task_status", description="This tool will update a task status based on its ID. Only the task's owner can change it.")
def update_task_status(task_id: TaskId, status: Status) -> Task:
    """
    This function will update the status of a specific task based on its ID
    """

    user = current_user()

    task = get_task(task_id)
    if task is None:
        raise ToolError(f"No task found with task_id {task_id!r}")
    if task.owner != user:
        raise ToolError(
            f"Task {task_id!r} belongs to {task.owner or 'nobody'}; only its owner can change its status"
        )

    updated = update_task_status_in_db(task_id, status)
    if updated is None:  # deleted between the check and the update
        raise ToolError(f"No task found with task_id {task_id!r}")

    return updated

if __name__ == "__main__":
    init_db()  # make sure the tasks table exists before serving
    mcp.run(transport="http", port=PORT)  # blocks until the server is stopped
