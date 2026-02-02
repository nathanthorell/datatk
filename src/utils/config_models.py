"""Pydantic models for tool configuration validation.

These models define the schema for each tool's config.toml section,
providing validation, defaults, and clear error messages for invalid configs.
"""

from typing import Literal

from pydantic import BaseModel, Field


class SqlToolsGlobalConfig(BaseModel):
    """Global sql_tools configuration that applies to all tools."""

    logging_level: Literal["verbose", "summary", "errors_only"] = "summary"


class DataCompareItem(BaseModel):
    """A single comparison configuration in data_compare."""

    name: str
    left_connection: str
    right_connection: str
    left_query: str | None = None
    right_query: str | None = None
    left_query_file: str | None = None
    right_query_file: str | None = None
    left_db_type: Literal["mssql", "postgres", "databricks"] = "mssql"
    right_db_type: Literal["mssql", "postgres", "databricks"] = "mssql"
    left_database: str | None = None
    right_database: str | None = None
    schema_name: str | None = None
    table_name: str | None = None


class DataCompareConfig(BaseModel):
    """Configuration for the data_compare tool."""

    output_type: Literal["left_only", "right_only", "common", "differences", "all"] | None = None
    output_file_path: str = "./output/"
    output_format: Literal["csv", "json", "sql"] = "csv"
    timestamp_file: bool = False
    max_sql_in_values: int = 1000
    compare_list: list[DataCompareItem]
    logging_level: Literal["verbose", "summary", "errors_only"] | None = None


class DbDiagramConfig(BaseModel):
    """Configuration for the db_diagram tool."""

    conn: str
    database: str = ""
    schema_: str = Field(alias="schema")
    column_mode: Literal["all", "keys_only", "none"] = "all"
    diagram_format: Literal["dbml", "mermaid", "plantuml"] = "dbml"
    output_file: str = "database_erd"
    output_directory: str = "./output/diagrams"
    scope: Literal["schema", "hierarchy"] = "schema"
    base_table: str | None = None
    hierarchy_direction: Literal["up", "down", "both"] = "both"
    hierarchy_max_depth: int | None = None
    logging_level: Literal["verbose", "summary", "errors_only"] | None = None

    model_config = {"populate_by_name": True}


class ObjectCompareConfig(BaseModel):
    """Configuration for the object_compare tool."""

    schema_: str = Field(alias="schema")
    database: str | None = None
    db_type: Literal["mssql", "postgres"] = "mssql"
    object_types: list[str]
    environments: dict[str, str]
    logging_level: Literal["verbose", "summary", "errors_only"] | None = None

    model_config = {"populate_by_name": True}


class DataCleanupConfig(BaseModel):
    """Configuration for the data_cleanup tool."""

    conn: str
    database: str
    schema_: str = Field(alias="schema")
    table: str
    cleanup_mode: Literal["summary", "execute"] = "summary"
    batch_size: int = 1000
    batch_threshold: int = 3000
    name: str | None = None
    disable_foreign_keys_for_tables: list[str] = Field(default_factory=list)
    query_of_data_to_remove: str
    logging_level: Literal["verbose", "summary", "errors_only"] | None = None

    model_config = {"populate_by_name": True}


class SimpleToolConfig(BaseModel):
    """Configuration for simple tools like usp_tester, view_tester."""

    conn: str
    database: str | None = None
    schema_: str = Field(alias="schema")
    logging_level: Literal["verbose", "summary", "errors_only"] | None = None

    model_config = {"populate_by_name": True}


class UspTesterConfig(SimpleToolConfig):
    """Configuration for the usp_tester tool."""

    defaults: dict[str, str | int | float] = Field(default_factory=dict)


class ViewTesterConfig(SimpleToolConfig):
    """Configuration for the view_tester tool."""

    pass


class SqlToParquetObject(BaseModel):
    """A single object to export in sql_to_parquet."""

    name: str
    object: str
    filter: str | None = None


class SqlToParquetConfig(BaseModel):
    """Configuration for the sql_to_parquet tool."""

    conn: str
    database: str | None = None
    data_dir: str = "./data/"
    batch_size: int = 10000
    objects: list[SqlToParquetObject]
    logging_level: Literal["verbose", "summary", "errors_only"] | None = None


class SchemaSizeEnvironment(BaseModel):
    """A single environment to analyze in schema_size."""

    name: str
    conn: str
    databases: list[str]
    schemas: list[str] | None = None  # Optional filter of schemas


class SchemaSizeConfig(BaseModel):
    """Configuration for the schema_size tool."""

    mode: Literal["summary", "detail"] = "summary"
    db_type: Literal["mssql", "postgres"] = "mssql"
    environments: list[SchemaSizeEnvironment]

    # Detail mode options (ignored in summary mode)
    sort_by: Literal["data_size", "row_count", "index_size", "total_size"] = "data_size"
    top_n: int = 50

    logging_level: Literal["verbose", "summary", "errors_only"] | None = None


# --- Registry for tool name -> model mapping ---
CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "data_compare": DataCompareConfig,
    "db_diagram": DbDiagramConfig,
    "object_compare": ObjectCompareConfig,
    "data_cleanup": DataCleanupConfig,
    "usp_tester": UspTesterConfig,
    "view_tester": ViewTesterConfig,
    "sql_to_parquet": SqlToParquetConfig,
    "schema_size": SchemaSizeConfig,
}
