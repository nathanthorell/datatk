from __future__ import annotations

import contextlib
import os
import re
from dataclasses import dataclass, field
from typing import Generator, Optional, TypeAlias

import psycopg2
import pyodbc
from databricks import sql as databricks_sql
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

ConnectionType: TypeAlias = (
    "pyodbc.Connection | psycopg2.extensions.connection | databricks_sql.client.Connection"
)


@dataclass
class ParsedConnectionParams:
    """Parsed/resolved connection parameters."""

    server: str = ""
    database: str = ""
    port: int | None = None
    # MSSQL-specific
    driver: str | None = None
    encrypt: str | None = None
    # Databricks-specific
    access_token: str | None = None
    http_path: str | None = None
    schema: str | None = None


@dataclass
class Connection:
    connection_string: str
    db_type: Optional[str] = None  # "mssql", "postgres", or "databricks"
    driver: Optional[str] = None
    encrypt: Optional[str] = None
    _parsed: ParsedConnectionParams = field(default_factory=ParsedConnectionParams, init=False)

    def __post_init__(self) -> None:
        """Parse connection string based on db_type."""
        if self.db_type == "mssql":
            self._parsed = self._parse_mssql()
        elif self.db_type == "postgres":
            self._parsed = self._parse_postgres()
        elif self.db_type == "databricks":
            self._parsed = self._parse_databricks()

    def _parse_mssql(self) -> ParsedConnectionParams:
        """Parse MSSQL connection string and resolve defaults."""
        params = ParsedConnectionParams()
        params.driver = self.driver or os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
        params.encrypt = self.encrypt or os.getenv("DB_ENCRYPT", "yes")

        server_match = re.search(r"Server\s*=\s*([^;]+)", self.connection_string, re.IGNORECASE)
        if server_match:
            server_port = server_match.group(1).strip()
            params.server = server_port.split(",")[0].strip()
            if "," in server_port:
                params.port = int(server_port.split(",")[1].strip())
        db_match = re.search(r"Database\s*=\s*([^;]+)", self.connection_string, re.IGNORECASE)
        if db_match:
            params.database = db_match.group(1).strip()
        return params

    def _parse_postgres(self) -> ParsedConnectionParams:
        """Parse PostgreSQL connection string (URI or key-value format)."""
        params = ParsedConnectionParams()
        # Try URI format: postgresql://user:pass@HOST:port/dbname
        uri_match = re.match(
            r"postgresql://(?:[^@]*@)?([^:/]+)(?::(\d+))?(?:/([^?]+))?",
            self.connection_string,
            re.IGNORECASE,
        )
        if uri_match:
            params.server = uri_match.group(1).strip()
            if uri_match.group(2):
                params.port = int(uri_match.group(2))
            if uri_match.group(3):
                params.database = uri_match.group(3).strip()
            return params
        # Fall back to key-value format
        host_match = re.search(r"host\s*=\s*([^\s]+)", self.connection_string, re.IGNORECASE)
        if host_match:
            params.server = host_match.group(1).strip()
        db_match = re.search(r"dbname\s*=\s*([^\s]+)", self.connection_string, re.IGNORECASE)
        if db_match:
            params.database = db_match.group(1).strip()
        port_match = re.search(r"port\s*=\s*(\d+)", self.connection_string, re.IGNORECASE)
        if port_match:
            params.port = int(port_match.group(1))
        return params

    def _parse_databricks(self) -> ParsedConnectionParams:
        """Parse Databricks connection string (URI or key-value format)."""
        # Try URI format first
        uri_match = re.match(
            r"databricks://token:([^@]+)@([^:/]+)(?::(\d+))?(?:/([^?]*))?(?:\?(.*))?",
            self.connection_string,
            re.IGNORECASE,
        )
        if uri_match:
            return self._parse_databricks_uri(uri_match)
        return self._parse_databricks_keyvalue()

    def _parse_databricks_uri(self, match: re.Match[str]) -> ParsedConnectionParams:
        """Parse Databricks URI format connection string."""
        params = ParsedConnectionParams(
            access_token=match.group(1),
            server=match.group(2),
            port=int(match.group(3)) if match.group(3) else None,
            database=match.group(4) or "",
        )
        if match.group(5):
            query_params = dict(p.split("=", 1) for p in match.group(5).split("&") if "=" in p)
            params.http_path = query_params.get("http_path")
            params.schema = query_params.get("schema")
        return params

    def _parse_databricks_keyvalue(self) -> ParsedConnectionParams:
        """Parse Databricks key-value format connection string."""
        params = ParsedConnectionParams()
        field_map = [
            ("server_hostname", "server"),
            ("http_path", "http_path"),
            ("access_token", "access_token"),
            ("catalog", "database"),
            ("schema", "schema"),
        ]
        for key, attr in field_map:
            match = re.search(rf"{key}\s*=\s*([^;\s]+)", self.connection_string, re.IGNORECASE)
            if match:
                setattr(params, attr, match.group(1))
        return params

    @contextlib.contextmanager
    def get_connection(
        self,
    ) -> Generator[ConnectionType, None, None]:
        """Context manager for database connections to ensure they're always closed."""
        conn = None
        try:
            conn = self.connect()
            yield conn
        finally:
            if conn:
                conn.close()

    @property
    def server(self) -> str:
        """Get server name from parsed connection params."""
        return self._parsed.server

    @property
    def database(self) -> str:
        """Get database name from parsed connection params."""
        return self._parsed.database

    @property
    def full_connection_string(self) -> str:
        """Build the complete connection string."""
        if self.db_type == "mssql":
            return (
                f"{self.connection_string};"
                f"Driver={self._parsed.driver};Encrypt={self._parsed.encrypt}"
            )
        return self.connection_string

    def connect(self) -> ConnectionType:
        """Create and return a database connection."""
        if self.db_type == "mssql":
            return pyodbc.connect(self.full_connection_string)
        elif self.db_type == "postgres":
            return psycopg2.connect(self.connection_string)
        elif self.db_type == "databricks":
            return databricks_sql.connect(
                server_hostname=self._parsed.server,
                http_path=self._parsed.http_path,
                access_token=self._parsed.access_token,
                catalog=self._parsed.database,
                schema=self._parsed.schema,
            )
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def get_sqlalchemy_engine(self) -> Engine:
        """
        Get a SQLAlchemy engine for this connection.

        This creates a SQLAlchemy engine that can be used with pandas
        and other libraries that work with SQLAlchemy.

        Returns:
            SQLAlchemy engine instance
        """
        if self.db_type == "mssql":
            # Create SQLAlchemy engine using a connection creator to avoid URL encoding issues
            # This bypasses SQLAlchemy's URL parsing and passes the conn str directly to pyodbc
            def creator() -> pyodbc.Connection:
                return pyodbc.connect(self.full_connection_string)

            engine = create_engine("mssql+pyodbc://", creator=creator)
            return engine
        elif self.db_type == "postgres":
            if self.connection_string.startswith("postgresql://"):
                engine = create_engine(self.connection_string)
            else:
                # For connection strings in key=value format
                engine = create_engine(f"postgresql+psycopg2://{self.connection_string}")
            return engine
        elif self.db_type == "databricks":
            # Use creator pattern to pass connection directly to SQLAlchemy
            # This avoids URL parsing issues with access tokens
            def databricks_creator() -> databricks_sql.client.Connection:
                return databricks_sql.connect(
                    server_hostname=self._parsed.server,
                    http_path=self._parsed.http_path,
                    access_token=self._parsed.access_token,
                    catalog=self._parsed.database,
                    schema=self._parsed.schema,
                )

            engine = create_engine("databricks://", creator=databricks_creator)
            return engine
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def __str__(self) -> str:
        return f"Server: [{self.server}] Database: [{self.database}] Type: [{self.db_type}]"


def get_connection(env_var_name: str, db_type: Optional[str] = None) -> Connection:
    """Helper function to get a connection from an environment variable."""
    conn_str = os.getenv(env_var_name)
    if not conn_str:
        raise ValueError(f"Environment variable '{env_var_name}' not found or empty")

    # Determine db_type if not provided
    if db_type is None:
        # Try to guess based on the connection string
        if conn_str.lower().startswith("databricks://") or "server_hostname=" in conn_str.lower():
            db_type = "databricks"
        elif "postgresql" in conn_str.lower() or "host=" in conn_str.lower():
            db_type = "postgres"
        else:
            db_type = "mssql"

    return Connection(connection_string=conn_str, db_type=db_type)


def modify_connection_for_database(connection: Connection, database_name: str) -> Connection:
    """
    Creates a new Connection object with the specified database name.
    For Databricks, this modifies the catalog.
    """
    if connection.db_type == "mssql":
        # Create a copy of the connection string with the new database name
        connection_string = re.sub(
            r"Database\s*=\s*[^;]+",
            f"Database={database_name}",
            connection.connection_string,
            flags=re.IGNORECASE,
        )
    elif connection.db_type == "postgres":
        # For postgres, handle both URI and key-value formats
        if connection.connection_string.startswith("postgresql://"):
            # URI format: replace the database name in the path
            connection_string = re.sub(
                r"(postgresql://[^/]*)/[^?\s]*",
                rf"\1/{database_name}",
                connection.connection_string,
                flags=re.IGNORECASE,
            )
        elif "dbname=" in connection.connection_string:
            # Key-value format: replace existing dbname
            connection_string = re.sub(
                r"dbname\s*=\s*[^\s;]+",
                f"dbname={database_name}",
                connection.connection_string,
                flags=re.IGNORECASE,
            )
        else:
            # Key-value format without dbname: add it
            connection_string = f"{connection.connection_string} dbname={database_name}"
    elif connection.db_type == "databricks":
        # For Databricks, handle both URI and key-value formats
        # The "database" maps to "catalog" in Databricks
        if connection.connection_string.lower().startswith("databricks://"):
            # URI format: replace the catalog in the path
            connection_string = re.sub(
                r"(databricks://[^/]*)/[^?\s]*",
                rf"\1/{database_name}",
                connection.connection_string,
                flags=re.IGNORECASE,
            )
        elif "catalog=" in connection.connection_string.lower():
            # Key-value format: replace existing catalog
            connection_string = re.sub(
                r"catalog\s*=\s*[^;\s]+",
                f"catalog={database_name}",
                connection.connection_string,
                flags=re.IGNORECASE,
            )
        else:
            # Key-value format without catalog: add it
            connection_string = f"{connection.connection_string};catalog={database_name}"
    else:
        raise ValueError(f"Unsupported database type: {connection.db_type}")

    # Return a new Connection object with the modified connection string
    return Connection(
        connection_string=connection_string,
        db_type=connection.db_type,
        driver=connection.driver,
        encrypt=connection.encrypt,
    )
