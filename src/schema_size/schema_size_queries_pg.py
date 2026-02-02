"""PostgreSQL-specific queries for schema size analysis."""


def get_pg_schema_sizes_query(schemas: list[str] | None = None) -> str:
    """
    Get the PostgreSQL query for schema-level size aggregation.

    Args:
        schemas: Optional list of schema names to filter. If None, all user schemas are included.

    Returns:
        SQL query string for fetching schema sizes.
    """
    if schemas:
        schema_list = ", ".join(f"'{s}'" for s in schemas)
        schema_filter = f"AND n.nspname IN ({schema_list})"
    else:
        schema_filter = ""

    return f"""
        SELECT
            n.nspname AS schema_name,
            COALESCE(SUM(c.reltuples::bigint), 0) AS total_rows,
            COALESCE(SUM(pg_total_relation_size(c.oid)), 0) AS total_bytes,
            COALESCE(SUM(pg_relation_size(c.oid)), 0) AS data_bytes,
            COALESCE(SUM(pg_indexes_size(c.oid)), 0) AS index_bytes
        FROM pg_namespace n
        LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relkind = 'r'
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        {schema_filter}
        GROUP BY n.nspname
        ORDER BY total_bytes DESC;
    """


def get_pg_table_sizes_query(schema_name: str) -> str:
    """
    Get the PostgreSQL query for table-level size analysis within a schema.

    Args:
        schema_name: The schema to analyze.

    Returns:
        SQL query string for fetching table sizes.
    """
    return f"""
        SELECT
            c.relname AS table_name,
            c.reltuples::bigint AS row_count,
            pg_total_relation_size(c.oid) AS total_bytes,
            pg_relation_size(c.oid) AS data_bytes,
            pg_indexes_size(c.oid) AS index_bytes
        FROM pg_class c
        INNER JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = '{schema_name}' AND c.relkind = 'r'
        ORDER BY pg_total_relation_size(c.oid) DESC;
    """
