"""Migration runner for all domains."""
import os
import glob
from pathlib import Path
from .connection import get_connection

CORE_PATH = Path(__file__).parent.parent / "sql"  # substrate/core/sql
DOMAINS_PATH = Path(__file__).parent.parent.parent / "domains"


def get_domain_migrations():
    """Discover all domain and core migrations."""
    migrations = []

    # Domain migrations first (create tables)
    for domain_dir in sorted(DOMAINS_PATH.iterdir()):
        if domain_dir.is_dir():
            sql_dir = domain_dir / "sql"
            if sql_dir.exists():
                for sql_file in sorted(sql_dir.glob("*.sql")):
                    migrations.append({
                        "domain": domain_dir.name,
                        "file": sql_file,
                        "version": sql_file.stem.split("_")[0]
                    })

    # Core migrations last (RLS, cross-cutting concerns that need tables)
    if CORE_PATH.exists():
        for sql_file in sorted(CORE_PATH.glob("*.sql")):
            migrations.append({
                "domain": "_core",
                "file": sql_file,
                "version": sql_file.stem.split("_")[0]
            })

    return migrations


def run_migrations():
    """Run all pending migrations."""
    migrations = get_domain_migrations()

    with get_connection() as conn:
        # Create migrations tracking table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS substrate_migrations (
                id SERIAL PRIMARY KEY,
                domain TEXT NOT NULL,
                version TEXT NOT NULL,
                filename TEXT NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(domain, version)
            )
        """)
        conn.commit()

        for migration in migrations:
            # Check if already applied
            result = conn.execute(
                "SELECT 1 FROM substrate_migrations WHERE domain = %s AND version = %s",
                (migration["domain"], migration["version"])
            ).fetchone()

            if result:
                continue

            print(f"Applying {migration['domain']}/{migration['file'].name}...")
            sql = migration["file"].read_text()
            conn.execute(sql)
            conn.execute(
                "INSERT INTO substrate_migrations (domain, version, filename) VALUES (%s, %s, %s)",
                (migration["domain"], migration["version"], migration["file"].name)
            )
            conn.commit()
            print(f"  Done.")


if __name__ == "__main__":
    run_migrations()
