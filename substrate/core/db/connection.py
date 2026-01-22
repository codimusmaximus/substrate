"""Database connection utilities."""
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from ..config import DATABASE_URL

# App role connection string (non-superuser, RLS enforced)
APP_DATABASE_URL = DATABASE_URL.replace("postgres:postgres", "substrate_app:substrate_app")


@contextmanager
def get_connection():
    """Get an admin database connection (bypasses RLS)."""
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_user_connection(user_id: str):
    """
    Get a connection scoped to a specific user (RLS enforced).

    Uses non-superuser app role so RLS policies are applied.
    """
    conn = psycopg.connect(APP_DATABASE_URL, row_factory=dict_row)
    try:
        conn.execute("SELECT set_config('app.user_id', %s, false)", [str(user_id)])
        yield conn
    finally:
        conn.close()


def get_pool():
    """Get a connection pool for async usage."""
    from psycopg_pool import ConnectionPool
    return ConnectionPool(DATABASE_URL)
