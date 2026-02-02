"""MSSQL-specific queries for schema size analysis."""


def get_mssql_schema_sizes_query(schemas: list[str] | None = None) -> str:
    """
    Get the MSSQL query for schema-level size aggregation.

    Args:
        schemas: Optional list of schema names to filter. If None, all schemas are included.

    Returns:
        SQL query string for fetching schema sizes.
    """
    schema_filter = "WHERE t.is_external = 0"
    if schemas:
        schema_list = ", ".join(f"'{s}'" for s in schemas)
        schema_filter += f" AND s.name IN ({schema_list})"

    return f"""
        SELECT
            s.name AS schema_name,
            SUM(p.rows) AS total_rows,
            SUM(a.total_pages) * 8 * 1024 AS total_bytes,
            SUM(CASE WHEN i.index_id <= 1 THEN a.used_pages ELSE 0 END) * 8 * 1024 AS data_bytes,
            SUM(CASE WHEN i.index_id > 1 THEN a.used_pages ELSE 0 END) * 8 * 1024 AS index_bytes
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.indexes i ON t.object_id = i.object_id
        INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
        {schema_filter}
        GROUP BY s.name
        ORDER BY total_bytes DESC;
    """


def get_mssql_table_sizes_query(schema_name: str) -> str:
    """
    Get the MSSQL query for table-level size analysis within a schema.

    Args:
        schema_name: The schema to analyze.

    Returns:
        SQL query string for fetching table sizes.
    """
    return f"""
        SELECT
            t.name AS table_name,
            SUM(p.rows) AS row_count,
            SUM(a.total_pages) * 8 * 1024 AS total_bytes,
            SUM(CASE WHEN i.index_id <= 1 THEN a.used_pages ELSE 0 END) * 8 * 1024 AS data_bytes,
            SUM(CASE WHEN i.index_id > 1 THEN a.used_pages ELSE 0 END) * 8 * 1024 AS index_bytes
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.indexes i ON t.object_id = i.object_id
        INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
        WHERE s.name = '{schema_name}' AND t.is_external = 0
        GROUP BY t.name
        ORDER BY total_bytes DESC;
    """
