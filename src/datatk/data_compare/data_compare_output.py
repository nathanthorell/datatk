import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from rich.pretty import Pretty
from rich.table import Table

from ..utils.rich_utils import console
from .data_compare_types import ComparisonResult

# --- Display ---


def _compare_columns(left_df: pd.DataFrame, right_df: pd.DataFrame) -> Dict[str, List[str]]:
    left_lower = {col.lower(): col for col in left_df.columns}
    right_lower = {col.lower(): col for col in right_df.columns}

    return {
        "left_only": sorted([left_lower[c] for c in set(left_lower) - set(right_lower)]),
        "right_only": sorted([right_lower[c] for c in set(right_lower) - set(left_lower)]),
        "matching": sorted([left_lower[c] for c in set(left_lower) & set(right_lower)]),
    }


def _performance_summary(result: ComparisonResult) -> tuple[str, str]:
    left_dur, right_dur = result.left.duration, result.right.duration
    if left_dur <= 0 or right_dur <= 0:
        return "N/A", "white"
    if right_dur < left_dur:
        factor = left_dur / right_dur
        return f"Right query is {factor:.2f}x faster than left", "green"
    if right_dur > left_dur:
        factor = right_dur / left_dur
        color = "yellow" if factor < 2 else "red"
        return f"Right query is {factor:.2f}x slower than left", color
    return "Both queries performed at the same speed", "white"


def _display_summary(result: ComparisonResult) -> None:
    status_color = "green" if result.is_equal else "red"
    row_color = "green" if result.row_count_match else "yellow"

    console.rule(
        f"[bold]Comparison Result: [{status_color}]"
        + f"{result.is_equal and 'EQUAL' or 'NOT EQUAL'}[/]"
    )

    if result.row_count_match:
        console.print(f"[bold]Rows:[/] Both queries returned {result.left.row_count} rows")
    else:
        console.print(
            f"[bold]Rows:[/] [bold {row_color}]{result.left.row_count}[/] vs "
            + f"[bold {row_color}]{result.right.row_count}[/]"
        )

    if result.case_insensitive:
        console.print("[bold]Mode:[/] [yellow]Case-insensitive string comparison[/]")

    if result.show_performance:
        perf_text, perf_color = _performance_summary(result)
        console.print(f"[bold]Performance:[/] [{perf_color}]{perf_text}[/]")

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2, 0, 0))
    table.add_column("Query", style="dim")
    table.add_column("Rows", justify="right")
    table.add_column("Duration", justify="right")
    table.add_row("Left", str(result.left.row_count), f"{result.left.duration:.2f}s")
    table.add_row("Right", str(result.right.row_count), f"{result.right.duration:.2f}s")
    console.print(table)


def _display_column_mismatch(result: ComparisonResult) -> None:
    cols = _compare_columns(result.left.results, result.right.results)

    console.print("[bold red]Column mismatch:[/]")
    table = Table(show_header=True)
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Columns")
    table.add_row(
        "[bold red]Left-only[/]",
        str(len(cols["left_only"])),
        ", ".join(cols["left_only"]) if cols["left_only"] else "[dim]None[/]",
    )
    table.add_row(
        "[bold red]Right-only[/]",
        str(len(cols["right_only"])),
        ", ".join(cols["right_only"]) if cols["right_only"] else "[dim]None[/]",
    )
    table.add_row(
        "[bold green]Matching[/]",
        str(len(cols["matching"])),
        ", ".join(cols["matching"]) if cols["matching"] else "[dim]None[/]",
    )
    console.print(table)


def _display_row_differences(result: ComparisonResult) -> None:
    left_count = len(result.left_only)
    right_count = len(result.right_only)
    common_count = len(result.common_rows)

    def pct_of(count: int, total: int, label: str) -> str:
        return f"{count / total * 100:.1f}% of {label}" if total > 0 else "N/A"

    console.print("[bold]Row Differences:[/]")
    table = Table(show_header=True)
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")
    table.add_row(
        "In left only", str(left_count), pct_of(left_count, result.left.row_count, "left")
    )
    table.add_row(
        "In right only", str(right_count), pct_of(right_count, result.right.row_count, "right")
    )
    table.add_row(
        "Common rows", str(common_count), pct_of(common_count, result.left.row_count, "left")
    )
    console.print(table)

    max_samples = 5
    if not result.left_only.empty:
        n = min(max_samples, len(result.left_only))
        console.print(
            f"\n[bold]Sample rows in left but not in right ({n} of {len(result.left_only)}):[/]"
        )
        console.print(Pretty(result.left_only.head(max_samples)))
    if not result.right_only.empty:
        n = min(max_samples, len(result.right_only))
        console.print(
            f"\n[bold]Sample rows in right but not in left ({n} of {len(result.right_only)}):[/]"
        )
        console.print(Pretty(result.right_only.head(max_samples)))


def display_result(result: ComparisonResult) -> None:
    """Display the comparison result using Rich formatting"""
    _display_summary(result)
    if not result.is_equal:
        if not result.columns_match:
            _display_column_mismatch(result)
        else:
            _display_row_differences(result)
    console.print()


# --- File output ---


def format_value_for_sql_in(value: Any) -> str:
    """Format a single value for use in SQL IN statement"""
    if pd.isna(value) or value is None:
        return "NULL"
    elif isinstance(value, str):
        # Escape single quotes by doubling them
        escaped_value = value.replace("'", "''")
        return f"'{escaped_value}'"
    elif isinstance(value, (bool, np.bool_)):
        return "1" if value else "0"
    elif isinstance(value, (int, float, np.integer, np.floating)):
        # Handle all numeric types (including numpy types)
        return str(value)
    else:
        # For other types (datetime, etc.), convert to string and quote
        escaped_value = str(value).replace("'", "''")
        return f"'{escaped_value}'"


def _format_table_name_for_sql(table_name: str) -> str:
    """Format table name with proper schema.table bracketing for SQL"""
    if "." in table_name:
        schema, table = table_name.split(".", 1)
        return f"[{schema}].[{table}]"
    return f"[{table_name}]"


def generate_sql_statement(
    dataset: pd.DataFrame, table_name: str, max_values: Optional[int] = None
) -> str:
    """Generate a complete SQL SELECT statement from a dataset"""
    if dataset.empty:
        return "-- No data to generate SELECT statement"

    unique_rows = dataset.drop_duplicates()

    if max_values is not None and len(unique_rows) > max_values:
        unique_rows = unique_rows.head(max_values)
        console.print(
            f"[yellow]Warning: Truncated to {max_values} rows for SQL SELECT statement[/]"
        )

    if len(dataset.columns) == 1:
        column_name = dataset.columns[0]
        values = unique_rows.iloc[:, 0].tolist()
        formatted_values = [format_value_for_sql_in(val) for val in values]

        if len(formatted_values) == 1:
            where_clause = f"WHERE {column_name} = {formatted_values[0]}"
        else:
            if len(formatted_values) <= 10:
                in_clause = f"IN ({', '.join(formatted_values)})"
            else:
                values_str = ",\n        ".join(formatted_values)
                in_clause = f"IN (\n        {values_str}\n    )"
            where_clause = f"WHERE {column_name} {in_clause}"

    else:
        column_names = list(dataset.columns)

        # AND/OR logic per row — SQL Server doesn't support tuple comparison (col1, col2) IN (...)
        row_conditions = []
        for _, row in unique_rows.iterrows():
            column_conditions = [
                f"{col_name} = {format_value_for_sql_in(row.iloc[i])}"
                for i, col_name in enumerate(column_names)
            ]
            row_conditions.append(f"({' AND '.join(column_conditions)})")

        if len(row_conditions) == 1:
            where_clause = f"WHERE {row_conditions[0]}"
        else:
            # larger lists break across lines for readability
            separator = " OR " if len(row_conditions) <= 3 else "\n   OR "
            where_clause = f"WHERE {separator.join(row_conditions)}"

    from_clause = _format_table_name_for_sql(table_name)
    return f"SELECT *\nFROM {from_clause}\n{where_clause};"


def generate_output_file(
    name: str,
    output_type: str,
    dataset: pd.DataFrame,
    output_dir: str,
    table_name: str,
    format: str = "csv",
    timestamp_file: bool = False,
    max_sql_in_values: Optional[int] = None,
) -> str:
    """Generate an output file from a dataset."""
    from pathlib import Path

    output_path = Path(output_dir)
    os.makedirs(output_path, exist_ok=True)

    clean_name = re.sub(r"_+", "_", re.sub(r"[^a-z0-9_-]", "", name.lower().replace(" ", "_")))

    if timestamp_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{output_type}_{timestamp}"
    else:
        filename = f"{clean_name}_{output_type}"

    if format.lower() == "csv":
        file_path = output_path / f"{filename}.csv"
        dataset.to_csv(file_path, index=False)
    elif format.lower() == "json":
        file_path = output_path / f"{filename}.json"
        dataset.to_json(file_path, orient="records", lines=True)
    elif format.lower() == "sql":
        file_path = output_path / f"{filename}.sql"
        sql_statement = generate_sql_statement(
            dataset, table_name=table_name, max_values=max_sql_in_values
        )
        unique_rows_count = len(dataset.drop_duplicates()) if not dataset.empty else 0
        key_columns = ", ".join(dataset.columns) if not dataset.empty else "N/A"
        sql_content = (
            f'-- SQL SELECT Statement for "{name}"\n'
            f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"-- Total records: {len(dataset)}\n"
            f"-- Unique row combinations: {unique_rows_count}\n"
            f"-- Key columns: {key_columns}\n"
            f"-- Usage: Copy this query and modify the table name as needed\n\n"
            f"{sql_statement}\n"
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(sql_content)
    else:
        raise ValueError(f"Unsupported format: {format}")

    console.print(f"[green]Output saved to:[/] {file_path}")
    return str(file_path)


def handle_output_files(
    result: ComparisonResult,
    name: str,
    output_type: str,
    output_dir: str,
    output_table_name: str,
    output_format: str,
    timestamp_file: bool,
    max_sql_in_values: int,
) -> None:
    """Handle output file generation based on output_type configuration

    Output types:
    - left_only: rows only in left query
    - right_only: rows only in right query
    - common: rows present in both queries
    - differences: both left_only AND right_only (what's different)
    - all: left_only, right_only, AND common (complete breakdown)
    """
    output_mappings = {
        "left_only": [("left_only", result.left_only)],
        "right_only": [("right_only", result.right_only)],
        "common": [("common", result.common_rows)],
        "differences": [("left_only", result.left_only), ("right_only", result.right_only)],
        "all": [
            ("left_only", result.left_only),
            ("right_only", result.right_only),
            ("common", result.common_rows),
        ],
    }

    if output_type not in output_mappings:
        console.print(f"[yellow]Unknown output type: {output_type}[/]")
        console.print("[dim]Valid options: left_only, right_only, common, differences, all[/]")
        return

    for file_type, dataset in output_mappings[output_type]:
        if not dataset.empty:
            generate_output_file(
                name=name,
                output_type=file_type,
                dataset=dataset,
                output_dir=output_dir,
                table_name=output_table_name,
                format=output_format,
                timestamp_file=timestamp_file,
                max_sql_in_values=max_sql_in_values,
            )
