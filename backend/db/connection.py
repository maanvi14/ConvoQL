"""Database connection manager with dialect detection and multi-database support."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import Dict, Any, Optional
import os

from config import get_settings

settings = get_settings()


class DBManager:
    """Manages database connections with dialect awareness."""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._dialect = "sqlite"
        self._schema_cache = None

    async def initialize(self, connection_string: Optional[str] = None):
        """Initialize database connection. Re-initializes if already connected.

        Args:
            connection_string: SQLAlchemy connection string. If None, uses default from settings.
        """
        # Close existing connection if any
        if self.engine:
            await self.engine.dispose()
            self._schema_cache = None
            print("[DBManager] Closed previous connection")

        conn_str = connection_string or settings.DATABASE_URL

        # Detect dialect
        conn_lower = conn_str.lower()
        if "sqlite" in conn_lower:
            self._dialect = "sqlite"
        elif "mysql" in conn_lower or "mariadb" in conn_lower or "pymysql" in conn_lower:
            self._dialect = "mysql"
        elif "postgres" in conn_lower or "psycopg" in conn_lower:
            self._dialect = "postgresql"
        else:
            self._dialect = "sqlite"

        # Create engine with appropriate parameters
        if self._dialect == "sqlite":
            self.engine = create_async_engine(
                conn_str,
                echo=False,
                future=True,
            )
        else:
            # MySQL/PostgreSQL need connection pooling
            self.engine = create_async_engine(
                conn_str,
                echo=False,
                future=True,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )

        self.SessionLocal = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        print(f"[DBManager] Initialized {self._dialect} connection")

    @property
    def dialect(self) -> str:
        """Get detected database dialect."""
        return self._dialect

    async def get_schema(self) -> Dict[str, Any]:
        """Get database schema with tables and columns."""
        if self._schema_cache:
            return self._schema_cache

        schema = {"tables": []}

        async with self.engine.connect() as conn:
            # Get tables
            if self._dialect == "sqlite":
                result = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ))
            elif self._dialect == "mysql":
                result = await conn.execute(text(
                    "SHOW TABLES"
                ))
            elif self._dialect == "postgresql":
                result = await conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                ))

            tables = result.fetchall()

            for table_row in tables:
                table_name = table_row[0]

                # Get columns
                if self._dialect == "sqlite":
                    cols_result = await conn.execute(
                        text(f"PRAGMA table_info({table_name})")
                    )
                    columns = []
                    for col in cols_result.fetchall():
                        columns.append({
                            "name": col[1],
                            "type": col[2],
                            "nullable": not col[3],
                            "default": col[4],
                        })
                elif self._dialect == "mysql":
                    cols_result = await conn.execute(
                        text(f"DESCRIBE {table_name}")
                    )
                    columns = []
                    for col in cols_result.fetchall():
                        columns.append({
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == "YES",
                            "default": col[4],
                        })
                elif self._dialect == "postgresql":
                    cols_result = await conn.execute(
                        text(f"""
                            SELECT column_name, data_type, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_name = '{table_name}'
                        """)
                    )
                    columns = []
                    for col in cols_result.fetchall():
                        columns.append({
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == "YES",
                            "default": col[3],
                        })

                # Get row count
                count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = count_result.scalar() or 0

                schema["tables"].append({
                    "name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                })

        self._schema_cache = schema
        return schema

    async def execute_readonly(self, sql: str) -> Dict[str, Any]:
        """Execute a read-only query and return results."""
        async with self.engine.connect() as conn:
            result = await conn.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys())

            # Convert to dict
            dict_rows = []
            for row in rows:
                dict_rows.append(dict(zip(columns, row)))

            return {
                "rows": dict_rows,
                "columns": columns,
            }

    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            self._schema_cache = None


# Global instance
db_manager = DBManager()
