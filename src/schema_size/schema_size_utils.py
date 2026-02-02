from typing import Literal

from schema_size.schema_size_queries_mssql import (
    get_mssql_schema_sizes_query,
    get_mssql_table_sizes_query,
)
from schema_size.schema_size_queries_pg import (
    get_pg_schema_sizes_query,
    get_pg_table_sizes_query,
)
from schema_size.schema_size_types import (
    DatabaseSize,
    SchemaSize,
    ServerResults,
    TableSize,
    format_size,
)
from utils import (
    Connection,
    modify_connection_for_database,
)
from utils.config_models import SchemaSizeEnvironment
from utils.rich_utils import align_columns, console, create_table


def get_schema_sizes_query(
    db_type: Literal["mssql", "postgres"], schemas: list[str] | None = None
) -> str:
    """
    Get the appropriate schema sizes query for the database type.

    Args:
        db_type: The database type ("mssql" or "postgres").
        schemas: Optional list of schema names to filter.

    Returns:
        SQL query string for fetching schema sizes.
    """
    if db_type == "postgres":
        return get_pg_schema_sizes_query(schemas)
    return get_mssql_schema_sizes_query(schemas)


def get_table_sizes_query(db_type: Literal["mssql", "postgres"], schema_name: str) -> str:
    """
    Get the appropriate table sizes query for the database type.

    Args:
        db_type: The database type ("mssql" or "postgres").
        schema_name: The schema to analyze.

    Returns:
        SQL query string for fetching table sizes.
    """
    if db_type == "postgres":
        return get_pg_table_sizes_query(schema_name)
    return get_mssql_table_sizes_query(schema_name)


def fetch_schema_sizes(
    conn: Connection,
    db_type: Literal["mssql", "postgres"],
    schemas: list[str] | None = None,
) -> list[SchemaSize]:
    """
    Fetch schema-level size metrics from the database.

    Args:
        conn: Database connection.
        db_type: The database type.
        schemas: Optional list of schema names to filter.

    Returns:
        List of SchemaSize objects.
    """
    query = get_schema_sizes_query(db_type, schemas)

    with conn.connect() as db_conn:
        cursor = db_conn.cursor()
        try:
            cursor.execute(query)
            return [
                SchemaSize(
                    schema_name=row[0],
                    total_rows=int(row[1]) if row[1] else 0,
                    total_bytes=float(row[2]) if row[2] else 0.0,
                    data_bytes=float(row[3]) if row[3] else 0.0,
                    index_bytes=float(row[4]) if row[4] else 0.0,
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            console.print(f"[red]Error fetching schema sizes:[/] {e}")
            return []
        finally:
            cursor.close()


def fetch_table_sizes(
    conn: Connection,
    db_type: Literal["mssql", "postgres"],
    schema_name: str,
) -> list[TableSize]:
    """
    Fetch table-level size metrics for a specific schema.

    Args:
        conn: Database connection.
        db_type: The database type.
        schema_name: The schema to analyze.

    Returns:
        List of TableSize objects.
    """
    query = get_table_sizes_query(db_type, schema_name)

    with conn.connect() as db_conn:
        cursor = db_conn.cursor()
        try:
            cursor.execute(query)
            return [
                TableSize(
                    table_name=row[0],
                    row_count=int(row[1]) if row[1] else 0,
                    total_bytes=float(row[2]) if row[2] else 0.0,
                    data_bytes=float(row[3]) if row[3] else 0.0,
                    index_bytes=float(row[4]) if row[4] else 0.0,
                )
                for row in cursor.fetchall()
            ]
        except Exception as e:
            console.print(f"[red]Error fetching table sizes:[/] {e}")
            return []
        finally:
            cursor.close()


def sort_tables(
    tables: list[TableSize],
    sort_by: Literal["data_size", "row_count", "index_size", "total_size"],
) -> list[TableSize]:
    """
    Sort tables by the specified metric.

    Args:
        tables: List of TableSize objects.
        sort_by: The metric to sort by.

    Returns:
        Sorted list of TableSize objects (descending).
    """
    sort_key_map = {
        "data_size": lambda t: t.data_bytes,
        "row_count": lambda t: t.row_count,
        "index_size": lambda t: t.index_bytes,
        "total_size": lambda t: t.total_bytes,
    }
    return sorted(tables, key=sort_key_map[sort_by], reverse=True)


def process_database_summary(
    env_name: str,
    db_name: str,
    connection: Connection,
    db_type: Literal["mssql", "postgres"],
    schemas: list[str] | None,
    logging_level: str,
) -> DatabaseSize | None:
    """
    Process a database in summary mode, returning aggregated size metrics.

    Args:
        env_name: Environment name for display.
        db_name: Database name.
        connection: Database connection.
        db_type: The database type.
        schemas: Optional list of schema names to filter.
        logging_level: Logging verbosity level.

    Returns:
        DatabaseSize with aggregated metrics, or None on error.
    """
    try:
        db_connection = modify_connection_for_database(connection, db_name)
        schema_sizes = fetch_schema_sizes(db_connection, db_type, schemas)

        total_rows = sum(schema.total_rows for schema in schema_sizes)
        total_bytes = sum(schema.total_bytes for schema in schema_sizes)
        data_bytes = sum(schema.data_bytes for schema in schema_sizes)
        index_bytes = sum(schema.index_bytes for schema in schema_sizes)

        db_size = DatabaseSize(total_bytes, data_bytes, index_bytes, total_rows)

        if logging_level == "verbose":
            db_table = create_table(
                columns=["Schema", "Row Count", "Total Size", "Data Size", "Index Size"]
            )

            align_columns(
                db_table,
                {
                    "Row Count": "right",
                    "Total Size": "right",
                    "Data Size": "right",
                    "Index Size": "right",
                },
            )

            for schema in schema_sizes:
                db_table.add_row(
                    schema.schema_name,
                    f"{schema.total_rows:,}",
                    schema.total_formatted,
                    schema.data_formatted,
                    schema.index_formatted,
                )

            console.print(f"\nSchema Sizes for [{env_name}].[{db_name}]:\n")
            console.print(db_table)
            console.print(
                f"Database Total: {format_size(total_bytes)} "
                f"(Data: {format_size(data_bytes)}, "
                f"Index: {format_size(index_bytes)}, "
                f"Rows: {total_rows:,})\n"
            )
            console.rule()

        return db_size

    except Exception as e:
        console.print(f"[red]Error processing database '{db_name}' on '{env_name}':[/] {e}")
        return DatabaseSize(0.0, 0.0, 0.0)


def process_database_detail(
    env_name: str,
    db_name: str,
    connection: Connection,
    db_type: Literal["mssql", "postgres"],
    schemas: list[str] | None,
    sort_by: Literal["data_size", "row_count", "index_size", "total_size"],
    top_n: int,
) -> list[SchemaSize]:
    """
    Process a database in detail mode, returning table-level metrics.

    Args:
        env_name: Environment name for display.
        db_name: Database name.
        connection: Database connection.
        db_type: The database type.
        schemas: Optional list of schema names to filter.
        sort_by: Metric to sort tables by.
        top_n: Maximum number of tables to return per schema.

    Returns:
        List of SchemaSize objects with populated tables.
    """
    try:
        db_connection = modify_connection_for_database(connection, db_name)

        # First get schema list (either filtered or all)
        schema_sizes = fetch_schema_sizes(db_connection, db_type, schemas)

        results = []
        for schema in schema_sizes:
            # Fetch tables for this schema
            tables = fetch_table_sizes(db_connection, db_type, schema.schema_name)
            sorted_tables = sort_tables(tables, sort_by)
            limited_tables = sorted_tables[:top_n] if top_n > 0 else sorted_tables

            results.append(
                SchemaSize(
                    schema_name=schema.schema_name,
                    total_rows=schema.total_rows,
                    total_bytes=schema.total_bytes,
                    data_bytes=schema.data_bytes,
                    index_bytes=schema.index_bytes,
                    tables=limited_tables,
                )
            )

        return results

    except Exception as e:
        console.print(f"[red]Error processing database '{db_name}' on '{env_name}':[/] {e}")
        return []


def process_environment_summary(
    env: SchemaSizeEnvironment,
    connection: Connection,
    db_type: Literal["mssql", "postgres"],
    logging_level: str,
) -> ServerResults:
    """
    Process all databases in an environment for summary mode.

    Args:
        env: Environment configuration.
        connection: Database connection.
        db_type: The database type.
        logging_level: Logging verbosity level.

    Returns:
        ServerResults containing all database sizes.
    """
    console.print(f"Processing environment: {env.name} ({len(env.databases)} databases)")

    databases: dict[str, DatabaseSize] = {}
    for db_name in env.databases:
        db_size = process_database_summary(
            env.name, db_name, connection, db_type, env.schemas, logging_level
        )
        if db_size:
            databases[db_name] = db_size

    return ServerResults(env.name, databases)


def process_environment_detail(
    env: SchemaSizeEnvironment,
    connection: Connection,
    db_type: Literal["mssql", "postgres"],
    sort_by: Literal["data_size", "row_count", "index_size", "total_size"],
    top_n: int,
) -> dict[str, list[SchemaSize]]:
    """
    Process all databases in an environment for detail mode.

    Args:
        env: Environment configuration.
        connection: Database connection.
        db_type: The database type.
        sort_by: Metric to sort tables by.
        top_n: Maximum number of tables per schema.

    Returns:
        Dictionary mapping database names to lists of SchemaSize with tables.
    """
    console.print(f"Processing environment: {env.name} ({len(env.databases)} databases)")

    results: dict[str, list[SchemaSize]] = {}
    for db_name in env.databases:
        schema_results = process_database_detail(
            env.name, db_name, connection, db_type, env.schemas, sort_by, top_n
        )
        if schema_results:
            results[db_name] = schema_results

    return results
