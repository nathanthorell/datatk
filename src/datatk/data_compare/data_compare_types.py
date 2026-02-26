from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, cast

import pandas as pd
from rich.pretty import Pretty
from rich.table import Table

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


class ComparisonResult:
    """Represents the result of comparing two query results"""

    def __init__(
        self,
        left: QueryResult,
        right: QueryResult,
        *,
        case_insensitive: bool = False,
        show_performance: bool = True,
    ):
        self.left = left
        self.right = right
        self.case_insensitive = case_insensitive
        self.show_performance = show_performance

        # Initialize variables
        self.left_only = pd.DataFrame()
        self.right_only = pd.DataFrame()
        self.common_rows = pd.DataFrame()
        self.is_equal = False
        self.row_count_match = self.left.row_count == self.right.row_count
        self.shape_match = False
        self.columns_match = False

        left_df = self.left.results.reset_index(drop=True)
        right_df = self.right.results.reset_index(drop=True)

        try:
            self.shape_match = left_df.shape == right_df.shape
            self.columns_match = self._check_column_match(left_df, right_df)

            if self.columns_match:
                self._compare_dataframes(left_df, right_df)

        except Exception as e:
            console.print(f"[dim]Error during DataFrame comparison: {e}[/]")

    def __str__(self) -> str:
        status = "EQUAL" if self.is_equal else "NOT EQUAL"
        return (
            f"Comparison Result: {status}\n"
            f"Left:  {self.left.row_count} rows, {self.left.duration:.2f}s\n"
            f"Right: {self.right.row_count} rows, {self.right.duration:.2f}s"
        )

    def _check_column_match(self, left_df: pd.DataFrame, right_df: pd.DataFrame) -> bool:
        """Check if column names match between dataframes (case-insensitive)"""
        left_cols_lower = {col.lower() for col in left_df.columns}
        right_cols_lower = {col.lower() for col in right_df.columns}
        return left_cols_lower == right_cols_lower

    def _compare_columns(
        self, left_df: pd.DataFrame, right_df: pd.DataFrame
    ) -> Dict[str, List[str]]:
        """Compare columns between dataframes and categorize them"""
        left_cols_lower = {col.lower(): col for col in left_df.columns}
        right_cols_lower = {col.lower(): col for col in right_df.columns}

        left_only_lower = set(left_cols_lower.keys()) - set(right_cols_lower.keys())
        right_only_lower = set(right_cols_lower.keys()) - set(left_cols_lower.keys())
        matching_lower = set(left_cols_lower.keys()) & set(right_cols_lower.keys())

        # Return original case column names
        return {
            "left_only": sorted([left_cols_lower[col] for col in left_only_lower]),
            "right_only": sorted([right_cols_lower[col] for col in right_only_lower]),
            "matching": sorted([left_cols_lower[col] for col in matching_lower]),
        }

    def _normalize_column_names(
        self, left_df: pd.DataFrame, right_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Create a copy of right_df with column names matching left_df's case"""
        col_mapping = {}
        for left_col in left_df.columns:
            for right_col in right_df.columns:
                if left_col.lower() == right_col.lower():
                    col_mapping[right_col] = left_col
                    break

        # Return a copy with renamed columns to match left case
        if col_mapping:
            return right_df.rename(columns=col_mapping)
        return right_df.copy()

    def _normalize_data_types(
        self, left_df: pd.DataFrame, right_df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Normalize data types between dataframes for consistent comparison"""
        left_normalized = left_df.copy()
        right_normalized = right_df.copy()

        for col in left_df.columns:
            left_is_dt = pd.api.types.is_datetime64_any_dtype(left_df[col])
            right_is_dt = pd.api.types.is_datetime64_any_dtype(right_df[col])

            # Datetime normalization — checked BEFORE object dtype so that columns
            # where one side is datetime64 and the other is object (e.g. SQL Server
            # returning out-of-ns-range dates as strings) are both converted to a
            # consistent datetime64[us] unit rather than falling into the string path.
            if left_is_dt or right_is_dt:
                try:
                    left_normalized[col] = pd.to_datetime(
                        left_normalized[col], errors="coerce"
                    ).astype("datetime64[us]")
                    right_normalized[col] = pd.to_datetime(
                        right_normalized[col], errors="coerce"
                    ).astype("datetime64[us]")
                except Exception:
                    left_normalized[col] = left_normalized[col].astype(str).str.strip()
                    right_normalized[col] = right_normalized[col].astype(str).str.strip()
            # String type normalization
            elif left_df[col].dtype == object or right_df[col].dtype == object:
                left_normalized[col] = left_normalized[col].astype(str).str.strip()
                right_normalized[col] = right_normalized[col].astype(str).str.strip()
            # Numeric type normalization
            elif pd.api.types.is_numeric_dtype(left_df[col]) and pd.api.types.is_numeric_dtype(
                right_df[col]
            ):
                left_normalized[col] = pd.to_numeric(left_normalized[col], errors="coerce")
                right_normalized[col] = pd.to_numeric(right_normalized[col], errors="coerce")

        return left_normalized, right_normalized

    def _compare_dataframes(self, left_df: pd.DataFrame, right_df: pd.DataFrame) -> None:
        """Compare two dataframes and identify matching/non-matching rows"""
        # Normalize column names to match case
        right_df_normalized = self._normalize_column_names(left_df, right_df)

        # Normalize data types for proper comparison
        left_normalized, right_normalized = self._normalize_data_types(left_df, right_df_normalized)

        # Sort columns for consistent comparison
        cols = sorted(left_normalized.columns.tolist())
        left_sorted = left_normalized[cols]
        right_sorted = right_normalized[cols]

        if self.case_insensitive:
            # Build lowercase copies for the merge only — originals used for output
            left_cmp = left_sorted.copy()
            right_cmp = right_sorted.copy()
            for col in cols:
                if left_cmp[col].dtype == object:
                    left_cmp[col] = left_cmp[col].str.lower()
                    right_cmp[col] = right_cmp[col].str.lower()

            left_cmp["__left_idx__"] = range(len(left_cmp))
            right_cmp["__right_idx__"] = range(len(right_cmp))
            merged = left_cmp.merge(right_cmp, on=cols, how="outer", indicator=True)

            left_idx = (
                merged.loc[merged["_merge"] == "left_only", "__left_idx__"].dropna().astype(int)
            )
            right_idx = (
                merged.loc[merged["_merge"] == "right_only", "__right_idx__"].dropna().astype(int)
            )
            both_idx = merged.loc[merged["_merge"] == "both", "__left_idx__"].dropna().astype(int)

            self.left_only = left_sorted.iloc[left_idx].reset_index(drop=True)
            self.right_only = right_sorted.iloc[right_idx].reset_index(drop=True)
            self.common_rows = left_sorted.iloc[both_idx].reset_index(drop=True)

        else:
            try:
                # Perform the merge to identify differences
                merged = left_sorted.merge(right_sorted, how="outer", indicator=True)

                # Extract the results
                self.left_only = merged[merged["_merge"] == "left_only"].drop("_merge", axis=1)
                self.right_only = merged[merged["_merge"] == "right_only"].drop("_merge", axis=1)
                self.common_rows = merged[merged["_merge"] == "both"].drop("_merge", axis=1)

            except Exception as e:
                console.print(f"[dim]Merge operation failed: {e}[/]")
                console.print("[dim]Falling back to alternative comparison method...[/]")

                # Alternative approach: use set-like operations with string representations
                # Convert rows to hashable strings for set operations
                left_strings = set(left_sorted.apply(lambda x: "|".join(x.astype(str)), axis=1))
                right_strings = set(right_sorted.apply(lambda x: "|".join(x.astype(str)), axis=1))

                # Find differences using set operations
                left_only_strings = left_strings - right_strings
                right_only_strings = right_strings - left_strings
                common_strings = left_strings & right_strings

                # Convert back to DataFrames by filtering original data
                if left_only_strings:
                    left_mask = left_sorted.apply(lambda x: "|".join(x.astype(str)), axis=1).isin(
                        left_only_strings
                    )
                    self.left_only = left_sorted[left_mask].drop_duplicates()
                else:
                    self.left_only = pd.DataFrame(columns=left_sorted.columns)

                if right_only_strings:
                    right_mask = right_sorted.apply(lambda x: "|".join(x.astype(str)), axis=1).isin(
                        right_only_strings
                    )
                    self.right_only = right_sorted[right_mask].drop_duplicates()
                else:
                    self.right_only = pd.DataFrame(columns=right_sorted.columns)

                if common_strings:
                    common_mask = left_sorted.apply(lambda x: "|".join(x.astype(str)), axis=1).isin(
                        common_strings
                    )
                    self.common_rows = left_sorted[common_mask].drop_duplicates()
                else:
                    self.common_rows = pd.DataFrame(columns=left_sorted.columns)

        # Sets is_equal if we have no differences (both sets match entirely)
        left_only_count = len(self.left_only)
        right_only_count = len(self.right_only)
        both_count = len(self.common_rows)

        self.is_equal = left_only_count == 0 and right_only_count == 0 and both_count > 0

    def calculate_performance_metrics(self) -> dict[str, str]:
        """Calculate performance metrics between left and right queries."""
        metrics = {
            "perf_text": "N/A",
            "perf_color": "white",
        }

        if self.left.duration > 0 and self.right.duration > 0:
            if self.right.duration < self.left.duration:
                # Right is faster
                speedup_factor = self.left.duration / self.right.duration
                metrics["perf_text"] = f"Right query is {speedup_factor:.2f}x faster than left"
                metrics["perf_color"] = "green"
            elif self.right.duration > self.left.duration:
                # Right is slower
                slowdown_factor = self.right.duration / self.left.duration
                metrics["perf_text"] = f"Right query is {slowdown_factor:.2f}x slower than left"
                metrics["perf_color"] = "yellow" if slowdown_factor < 2 else "red"
            else:
                # Equal times
                metrics["perf_text"] = "Both queries performed at the same speed"

        return metrics

    def _display_summary(self) -> None:
        status_color = "green" if self.is_equal else "red"
        row_color = "green" if self.row_count_match else "yellow"

        console.rule(
            f"[bold]Comparison Result: [{status_color}]"
            + f"{self.is_equal and 'EQUAL' or 'NOT EQUAL'}[/]"
        )

        if self.row_count_match:
            console.print(f"[bold]Rows:[/] Both queries returned {self.left.row_count} rows")
        else:
            console.print(
                f"[bold]Rows:[/] [bold {row_color}]{self.left.row_count}[/] vs "
                + f"[bold {row_color}]{self.right.row_count}[/]"
            )

        if self.case_insensitive:
            console.print("[bold]Mode:[/] [yellow]Case-insensitive string comparison[/]")

        if self.show_performance:
            perf_metrics = self.calculate_performance_metrics()
            color = perf_metrics["perf_color"]
            text = perf_metrics["perf_text"]
            console.print(f"[bold]Performance:[/] [{color}]{text}[/]")

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2, 0, 0))
        table.add_column("Query", style="dim")
        table.add_column("Rows", justify="right")
        table.add_column("Duration", justify="right")
        table.add_row("Left", str(self.left.row_count), f"{self.left.duration:.2f}s")
        table.add_row("Right", str(self.right.row_count), f"{self.right.duration:.2f}s")
        console.print(table)

    def _display_column_mismatch(self) -> None:
        column_comparison = self._compare_columns(self.left.results, self.right.results)
        left_only = column_comparison["left_only"]
        right_only = column_comparison["right_only"]
        matching = column_comparison["matching"]

        console.print("[bold red]Column mismatch:[/]")
        table = Table(show_header=True)
        table.add_column("Category", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Columns")
        table.add_row(
            "[bold red]Left-only[/]",
            str(len(left_only)),
            ", ".join(left_only) if left_only else "[dim]None[/]",
        )
        table.add_row(
            "[bold red]Right-only[/]",
            str(len(right_only)),
            ", ".join(right_only) if right_only else "[dim]None[/]",
        )
        table.add_row(
            "[bold green]Matching[/]",
            str(len(matching)),
            ", ".join(matching) if matching else "[dim]None[/]",
        )
        console.print(table)

    def _display_row_differences(self) -> None:
        left_only_count = len(self.left_only)
        right_only_count = len(self.right_only)
        common_count = len(self.common_rows)

        left_pct = (
            f"{left_only_count / self.left.row_count * 100:.1f}% of left"
            if self.left.row_count > 0
            else "N/A"
        )
        right_pct = (
            f"{right_only_count / self.right.row_count * 100:.1f}% of right"
            if self.right.row_count > 0
            else "N/A"
        )
        common_pct = (
            f"{common_count / self.left.row_count * 100:.1f}% of left"
            if self.left.row_count > 0
            else "N/A"
        )

        console.print("[bold]Row Differences:[/]")
        table = Table(show_header=True)
        table.add_column("Category", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Percentage", justify="right")
        table.add_row("In left only", str(left_only_count), left_pct)
        table.add_row("In right only", str(right_only_count), right_pct)
        table.add_row("Common rows", str(common_count), common_pct)
        console.print(table)

        max_samples = 5
        if not self.left_only.empty:
            n = min(max_samples, len(self.left_only))
            console.print(
                f"\n[bold]Sample rows in left but not in right ({n} of {len(self.left_only)}):[/]"
            )
            console.print(Pretty(self.left_only.head(max_samples)))
        if not self.right_only.empty:
            n = min(max_samples, len(self.right_only))
            console.print(
                f"\n[bold]Sample rows in right but not in left ({n} of {len(self.right_only)}):[/]"
            )
            console.print(Pretty(self.right_only.head(max_samples)))

    def rich_display(self) -> None:
        """Display the comparison result using Rich formatting"""
        self._display_summary()
        if not self.is_equal:
            if not self.columns_match:
                self._display_column_mismatch()
            else:
                self._display_row_differences()
        console.print()


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
