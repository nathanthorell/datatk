"""Connection utilities for parsing database connections.

Provides functions for parsing raw connection strings into Pydantic models.
"""

from __future__ import annotations

import os
import re

from .connection_models import (
    Connection,
    DatabricksConnection,
    DbType,
    MSSQLConnection,
    PostgresConnection,
    detect_db_type,
    get_driver_default,
    get_encrypt_default,
)


def parse_connection(raw_string: str, db_type: DbType | None = None) -> Connection:
    """Parse a raw connection string into a Connection model.

    Args:
        raw_string: Raw connection string from environment variable
        db_type: Database type, auto-detected if not provided

    Returns:
        Appropriate Connection model (MSSQL, Postgres, or Databricks)
    """
    if db_type is None:
        db_type = detect_db_type(raw_string)

    if db_type == "mssql":
        return _parse_mssql(raw_string)
    elif db_type == "postgres":
        return _parse_postgres(raw_string)
    elif db_type == "databricks":
        return _parse_databricks(raw_string)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def _parse_mssql(conn_str: str) -> MSSQLConnection:
    """Parse MSSQL connection string."""
    server = ""
    database = ""
    port = None
    user = None
    password = None

    server_match = re.search(r"Server\s*=\s*([^;]+)", conn_str, re.IGNORECASE)
    if server_match:
        server_port = server_match.group(1).strip()
        server = server_port.split(",")[0].strip()
        if "," in server_port:
            port = int(server_port.split(",")[1].strip())

    db_match = re.search(r"Database\s*=\s*([^;]+)", conn_str, re.IGNORECASE)
    if db_match:
        database = db_match.group(1).strip()

    user_match = re.search(r"UID\s*=\s*([^;]+)", conn_str, re.IGNORECASE)
    if user_match:
        user = user_match.group(1).strip()

    password_match = re.search(r"PWD\s*=\s*([^;]+)", conn_str, re.IGNORECASE)
    if password_match:
        password = password_match.group(1).strip()

    return MSSQLConnection(
        server=server,
        database=database,
        port=port,
        user=user,
        password=password,
        driver=get_driver_default(),
        encrypt=get_encrypt_default(),
    )


def _parse_postgres(conn_str: str) -> PostgresConnection:
    """Parse PostgreSQL connection string (URI or key-value format)."""
    server = ""
    database = ""
    port = 5432
    user = None
    password = None

    # Try URI format: postgresql://user:pass@HOST:port/dbname
    uri_match = re.match(
        r"postgresql://(?:([^:@]+)(?::([^@]*))?@)?([^:/]+)(?::(\d+))?(?:/([^?]+))?",
        conn_str,
        re.IGNORECASE,
    )
    if uri_match:
        user = uri_match.group(1)
        password = uri_match.group(2)
        server = uri_match.group(3).strip()
        if uri_match.group(4):
            port = int(uri_match.group(4))
        if uri_match.group(5):
            database = uri_match.group(5).strip()
    else:
        # Fall back to key-value format
        host_match = re.search(r"host\s*=\s*([^\s]+)", conn_str, re.IGNORECASE)
        if host_match:
            server = host_match.group(1).strip()

        db_match = re.search(r"dbname\s*=\s*([^\s]+)", conn_str, re.IGNORECASE)
        if db_match:
            database = db_match.group(1).strip()

        port_match = re.search(r"port\s*=\s*(\d+)", conn_str, re.IGNORECASE)
        if port_match:
            port = int(port_match.group(1))

        user_match = re.search(r"user\s*=\s*([^\s]+)", conn_str, re.IGNORECASE)
        if user_match:
            user = user_match.group(1).strip()

        password_match = re.search(r"password\s*=\s*([^\s]+)", conn_str, re.IGNORECASE)
        if password_match:
            password = password_match.group(1).strip()

    return PostgresConnection(
        server=server,
        database=database,
        port=port,
        user=user,
        password=password,
    )


def _parse_databricks(conn_str: str) -> DatabricksConnection:
    """Parse Databricks connection string (URI or key-value format)."""
    # Try URI format first
    uri_match = re.match(
        r"databricks://token:([^@]+)@([^:/]+)(?::(\d+))?(?:/([^?]*))?(?:\?(.*))?",
        conn_str,
        re.IGNORECASE,
    )
    if uri_match:
        return _parse_databricks_uri(uri_match)
    return _parse_databricks_keyvalue(conn_str)


def _parse_databricks_uri(match: re.Match[str]) -> DatabricksConnection:
    """Parse Databricks URI format connection string."""
    http_path = None
    schema_name = None

    if match.group(5):
        query_params = dict(p.split("=", 1) for p in match.group(5).split("&") if "=" in p)
        http_path = query_params.get("http_path")
        schema_name = query_params.get("schema")

    return DatabricksConnection(
        server=match.group(2),
        catalog=match.group(4) or "",
        access_token=match.group(1),
        http_path=http_path or "",
        schema_name=schema_name,
    )


def _parse_databricks_keyvalue(conn_str: str) -> DatabricksConnection:
    """Parse Databricks key-value format connection string."""
    params: dict[str, str | None] = {
        "server": None,
        "catalog": None,
        "access_token": None,
        "http_path": None,
        "schema_name": None,
    }

    field_map = [
        ("server_hostname", "server"),
        ("http_path", "http_path"),
        ("access_token", "access_token"),
        ("catalog", "catalog"),
        ("schema", "schema_name"),
    ]

    for key, param_name in field_map:
        match = re.search(rf"{key}\s*=\s*([^;\s]+)", conn_str, re.IGNORECASE)
        if match:
            params[param_name] = match.group(1)

    return DatabricksConnection(
        server=params["server"] or "",
        catalog=params["catalog"] or "",
        access_token=params["access_token"] or "",
        http_path=params["http_path"] or "",
        schema_name=params["schema_name"],
    )


def load_connection(env_var_name: str, db_type: DbType | None = None) -> Connection:
    """Load a connection from an environment variable.

    Args:
        env_var_name: Name of environment variable containing connection string
        db_type: Database type, auto-detected if not provided

    Returns:
        Parsed Connection model

    Raises:
        ValueError: If environment variable is not found or empty
    """
    conn_str = os.getenv(env_var_name)
    if not conn_str:
        raise ValueError(f"Environment variable '{env_var_name}' not found or empty")

    return parse_connection(conn_str, db_type)


def modify_connection_for_database(conn: Connection, database_name: str) -> Connection:
    """Create a new Connection with a different database name.

    Args:
        conn: Existing connection model
        database_name: New database name (or catalog for Databricks)

    Returns:
        New Connection model with updated database
    """
    if isinstance(conn, MSSQLConnection):
        return MSSQLConnection(
            server=conn.server,
            database=database_name,
            port=conn.port,
            user=conn.user,
            password=conn.password,
            driver=conn.driver,
            encrypt=conn.encrypt,
        )
    elif isinstance(conn, PostgresConnection):
        return PostgresConnection(
            server=conn.server,
            database=database_name,
            port=conn.port,
            user=conn.user,
            password=conn.password,
        )
    elif isinstance(conn, DatabricksConnection):
        return DatabricksConnection(
            server=conn.server,
            catalog=database_name,
            access_token=conn.access_token,
            http_path=conn.http_path,
            schema_name=conn.schema_name,
        )
    else:
        raise ValueError(f"Unsupported connection type: {type(conn)}")
