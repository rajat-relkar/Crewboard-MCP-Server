"""OAuth login shared by the Python clients (client.py and langchain_client.py).

The first time a client connects, a browser window opens so you can log in with
GitHub. The resulting tokens are saved in TOKEN_DIR, so later runs reuse them
instead of asking you to log in again. Delete that folder to log out.
"""
from fastmcp import settings
from fastmcp.client.auth import OAuth
from key_value.aio.stores.filetree import (
    FileTreeStore,
    FileTreeV1CollectionSanitizationStrategy,
    FileTreeV1KeySanitizationStrategy,
)

# Outside the project folder, so tokens can never be committed by accident.
TOKEN_DIR = settings.home / "client-tokens" / "mcp_server_rrelkar"


def make_oauth() -> OAuth:
    """Create an OAuth handler for one fastmcp Client, backed by the saved tokens."""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_store = FileTreeStore(
        data_directory=TOKEN_DIR,
        key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(TOKEN_DIR),
        collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(TOKEN_DIR),
    )
    return OAuth(client_name="mcp_server_rrelkar Python client", token_storage=token_store)
