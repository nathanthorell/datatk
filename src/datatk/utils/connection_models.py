"""Pydantic models for database connection parameters.

These models represent the normalized/parsed connection parameters
for each supported database type. Parsing raw connection strings
into these models happens in connection_utils.py.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Literal

import pandas as pd
import psycopg2
import psycopg2.extensions
import pyodbc
from databricks import sql as databricks_sql
from pydantic import BaseModel, computed_field
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    pass


class MSSQLConnection(BaseModel):
    """MSSQL connection parameters."""

    db_type: Literal["mssql"] = "mssql"
    server: str
    database: str
    user: str | None = None
    password: str | None = None
    port: int | None = None
    driver: str = "ODBC Driver 18 for SQL Server"
    encrypt: str = "yes"
    auth_type: Literal["sql", "azure_ad_interactive"] = "sql"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def connection_string(self) -> str:
        """Build ODBC connection string."""
        server_part = f"{self.server},{self.port}" if self.port else self.server
        base = (
            f"Server={server_part};Database={self.database};"
            f"Driver={self.driver};Encrypt={self.encrypt}"
        )
        if self.auth_type == "azure_ad_interactive":
            # Token is passed separately via attrs_before — no UID/PWD in the string
            return base
        return base + f";UID={self.user};PWD={self.password}"

    @contextlib.contextmanager
    def connect(self) -> Generator[pyodbc.Connection, None, None]:
        """Context manager for database connection."""
        from .azure_client import AzureClient

        conn = None
        try:
            if self.auth_type == "azure_ad_interactive":
                conn = AzureClient().get_pyodbc_connection(self.connection_string)
            else:
                conn = pyodbc.connect(self.connection_string)
            yield conn
        finally:
            if conn:
                conn.close()

    def get_sqlalchemy_engine(self) -> Engine:
        """Get a SQLAlchemy engine for this connection."""
        from .azure_client import AzureClient

        if self.auth_type == "azure_ad_interactive":
            conn_str = self.connection_string

            def azure_creator() -> pyodbc.Connection:
                return AzureClient().get_pyodbc_connection(conn_str)

            return create_engine("mssql+pyodbc://", creator=azure_creator)

        def creator() -> pyodbc.Connection:
            return pyodbc.connect(self.connection_string)

        return create_engine("mssql+pyodbc://", creator=creator)


class PostgresConnection(BaseModel):
    """PostgreSQL connection parameters."""

    db_type: Literal["postgres"] = "postgres"
    server: str
    database: str
    port: int = 5432
    user: str | None = None
    password: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def connection_string(self) -> str:
        """Build PostgreSQL connection URI."""
        auth = ""
        if self.user:
            auth = self.user
            if self.password:
                auth += f":{self.password}"
            auth += "@"
        return f"postgresql://{auth}{self.server}:{self.port}/{self.database}"

    @contextlib.contextmanager
    def connect(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Context manager for database connection."""
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            yield conn
        finally:
            if conn:
                conn.close()

    def get_sqlalchemy_engine(self) -> Engine:
        """Get a SQLAlchemy engine for this connection."""
        return create_engine(self.connection_string)


class DatabricksConnection(BaseModel):
    """Databricks connection parameters."""

    db_type: Literal["databricks"] = "databricks"
    server: str  # server_hostname
    catalog: str  # called "database" in other db types
    access_token: str
    http_path: str
    schema_name: str | None = None

    @property
    def database(self) -> str:
        """Alias for catalog to maintain consistency with other connection types."""
        return self.catalog

    @contextlib.contextmanager
    def connect(self) -> Generator[databricks_sql.client.Connection, None, None]:
        """Context manager for database connection."""
        conn = None
        try:
            conn = databricks_sql.connect(
                server_hostname=self.server,
                http_path=self.http_path,
                access_token=self.access_token,
                catalog=self.catalog,
                schema=self.schema_name,
            )
            yield conn
        finally:
            if conn:
                conn.close()

    def get_sqlalchemy_engine(self) -> Engine:
        """Get a SQLAlchemy engine for this connection."""

        def creator() -> databricks_sql.client.Connection:
            return databricks_sql.connect(
                server_hostname=self.server,
                http_path=self.http_path,
                access_token=self.access_token,
                catalog=self.catalog,
                schema=self.schema_name,
            )

        return create_engine("databricks://", creator=creator)


class FileConnection(BaseModel):
    """File-based data source for Parquet, CSV, and JSON files."""

    db_type: Literal["file"] = "file"
    file_path: str

    @property
    def database(self) -> str:
        """Filename, for display consistency with other connection types."""
        return Path(self.file_path).name

    @property
    def file_format(self) -> str:
        """File format inferred from extension."""
        return Path(self.file_path).suffix.lstrip(".").lower()

    def read_file(self) -> pd.DataFrame:
        """Read the file into a DataFrame."""
        fmt = self.file_format
        if fmt == "parquet":
            return pd.read_parquet(self.file_path)
        elif fmt == "csv":
            return pd.read_csv(self.file_path)
        elif fmt == "json":
            return pd.read_json(self.file_path)
        else:
            raise ValueError(f"Unsupported file format: .{fmt} (supported: parquet, csv, json)")


# DB-only connections (server/engine required)
DbConnection = MSSQLConnection | PostgresConnection | DatabricksConnection

# All connection types including file sources
Connection = DbConnection | FileConnection

# Valid db_type values
DbType = Literal["mssql", "postgres", "databricks"]


def detect_db_type(conn_str: str) -> DbType:
    """Detect database type from connection string format."""
    lower = conn_str.lower()
    if lower.startswith("databricks://") or "server_hostname=" in lower:
        return "databricks"
    elif lower.startswith("postgresql://") or "host=" in lower or "dbname=" in lower:
        return "postgres"
    else:
        return "mssql"


def get_driver_default() -> str:
    """Get MSSQL driver from environment or use default."""
    return os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")


def get_encrypt_default() -> str:
    """Get MSSQL encrypt setting from environment or use default."""
    return os.getenv("DB_ENCRYPT", "yes")
