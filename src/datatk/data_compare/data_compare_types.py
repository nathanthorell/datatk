from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, cast

import pandas as pd

from ..utils import Connection, FileConnection, load_connection, modify_connection_for_database
from ..utils.connection_models import DbType
from ..utils.rich_utils import COLORS, console


@dataclass
class QueryResult:
    """Contains the results and metadata from a query execution"""

    results: pd.DataFrame
    duration: float

    @property
    def row_count(self) -> int:
        return len(self.results)


@dataclass(eq=False)
class ComparisonResult:
    """Represents the result of comparing two query results"""

    left: QueryResult
    right: QueryResult
    left_only: pd.DataFrame = field(default_factory=pd.DataFrame)
    right_only: pd.DataFrame = field(default_factory=pd.DataFrame)
    common_rows: pd.DataFrame = field(default_factory=pd.DataFrame)
    is_equal: bool = False
    row_count_match: bool = False
    shape_match: bool = False
    columns_match: bool = False
    case_insensitive: bool = False
    show_performance: bool = True

    def __str__(self) -> str:
        status = "EQUAL" if self.is_equal else "NOT EQUAL"
        return (
            f"Comparison Result: {status}\n"
            f"Left:  {self.left.row_count} rows, {self.left.duration:.2f}s\n"
            f"Right: {self.right.row_count} rows, {self.right.duration:.2f}s"
        )


@dataclass
class ComparisonItem:
    """Type definition for a single comparison configuration"""

    name: str
    left_connection: Connection
    right_connection: Connection
    left_query: str
    right_query: str
    table_name: str
    schema_name: str = ""
    left_db_type: str = "mssql"
    right_db_type: str = "mssql"
    case_insensitive: bool = False

    @property
    def full_table_name(self) -> str:
        """Return the full table name with schema if provided"""
        if self.schema_name:
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name


class ComparisonConfig:
    """Configuration for data comparisons"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sql_dir = config.get("sql_dir", "./sql")
        self.case_insensitive = config.get("case_insensitive", False)
        self.comparisons = self._process_comparisons()

    def _resolve_side(self, item: Dict[str, Any], side: str) -> tuple[str, Connection]:
        """Resolve query and connection for one side ('left' or 'right') of a comparison."""
        query: str | None = item.get(f"{side}_query")
        if not query and f"{side}_query_file" in item:
            query = self._load_sql_file(item[f"{side}_query_file"])
        if not query:
            raise ValueError(f"Comparison '{item['name']}' is missing a {side} query")

        raw_db_type: str = item.get(f"{side}_db_type", "mssql")
        if raw_db_type == "file":
            conn: Connection = FileConnection(file_path=query)
        else:
            conn = load_connection(item[f"{side}_connection"], db_type=cast(DbType, raw_db_type))

        if f"{side}_database" in item and not isinstance(conn, FileConnection):
            conn = modify_connection_for_database(conn, item[f"{side}_database"])

        return query, conn

    def _process_comparisons(self) -> List[ComparisonItem]:
        """Process comparison items from config, loading SQL files where needed"""
        items = self.config.get("compare_list", [])
        if not items:
            raise ValueError("No comparisons defined in config")

        comparisons = []
        for item in items:
            left_query, left_conn = self._resolve_side(item, "left")
            right_query, right_conn = self._resolve_side(item, "right")

            comparison = ComparisonItem(
                name=item["name"],
                left_connection=left_conn,
                right_connection=right_conn,
                left_query=left_query,
                right_query=right_query,
                left_db_type=item.get("left_db_type", "mssql"),
                right_db_type=item.get("right_db_type", "mssql"),
                table_name=item.get("table_name", "table_name_not_provided"),
                schema_name=item.get("schema_name", ""),
                case_insensitive=item.get("case_insensitive", self.case_insensitive),
            )
            comparisons.append(comparison)

        return comparisons

    def _load_sql_file(self, filename: str) -> str:
        """Load SQL query from a file"""
        sql_path = Path(self.sql_dir) / filename

        if not sql_path.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_path}")

        with open(sql_path) as f:
            return f.read()

    def rich_display(self) -> None:
        """Display the configuration using Rich formatting"""
        console.rule("[bold]Comparison Configuration")

        for i, comp in enumerate(self.comparisons):
            color = COLORS[i % len(COLORS)]
            console.print(f"[bold {color}]{comp.name}[/]")
            console.print(f"  Left:  [{color}]{comp.left_db_type}[/] - {comp.left_connection}")
            console.print(f"  Right: [{color}]{comp.right_db_type}[/] - {comp.right_connection}")

            # Show query previews if desired
            if self.config.get("show_query_previews", False):
                left_preview = comp.left_query.strip().split("\n")[0][:50] + "..."
                right_preview = comp.right_query.strip().split("\n")[0][:50] + "..."
                console.print(f"  Left query: {left_preview}")
                console.print(f"  Right query: {right_preview}")

        console.print()
