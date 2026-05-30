from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

import pandas as pd
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from ..utils import Connection, FileConnection
from ..utils.connection_models import DatabricksConnection
from ..utils.rich_utils import COLORS, console
from .data_compare_core import compare_dataframes
from .data_compare_output import display_result, handle_output_files
from .data_compare_types import ComparisonConfig, ComparisonResult, QueryResult


def execute_sql_query(
    conn: Connection,
    sql_query: str,
    params: Optional[list[Any]] = None,
    show_performance: bool = True,
) -> Tuple[pd.DataFrame, float]:
    """Execute a SQL query (or read a file) and return results with execution duration"""
    start_time = datetime.now()

    if isinstance(conn, FileConnection):
        if show_performance:
            console.print(f"[dim]Reading file:[/] [blue]{conn.file_path}[/]", end="\r")
        try:
            df = conn.read_file()
            duration = (datetime.now() - start_time).total_seconds()
            if show_performance:
                console.print(f"[green]File read in {duration:.2f}s[/]       ")
            return df, duration
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            console.print(f"[red]File read failed after {duration:.2f}s[/]       ")
            raise Exception(f"File read failed: {str(e)}") from e

    if show_performance:
        query_preview = sql_query[:50].replace("\n", " ") + ("..." if len(sql_query) > 50 else "")
        console.print(f"[dim]Executing query:[/] [blue]{query_preview}[/]")
    try:
        if isinstance(conn, DatabricksConnection):
            with conn.connect() as db_conn:
                cursor = db_conn.cursor()
                cursor.execute(sql_query, parameters=params)
                df = cursor.fetchall_arrow().to_pandas()
        else:
            engine = conn.get_sqlalchemy_engine()
            df = pd.read_sql_query(sql_query, engine, params=params)

        duration = (datetime.now() - start_time).total_seconds()
        if show_performance:
            console.print(f"[green]Query completed in {duration:.2f}s[/]       ")
        return df, duration

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        console.print(f"[red]Query failed after {duration:.2f}s[/]       ")
        raise Exception(f"Query failed after {duration:.2f}s: {str(e)}") from e


def compare_sql(
    left_conn: Connection,
    right_conn: Connection,
    left_query: str,
    right_query: str,
    *,
    left_params: Optional[list[Any]] = None,
    right_params: Optional[list[Any]] = None,
    case_insensitive: bool = False,
    show_performance: bool = True,
) -> ComparisonResult:
    """Compare the results of two SQL queries"""
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(complete_style="green"),
        TimeElapsedColumn(),
        console=console,
        expand=False,
        disable=not show_performance,
    ) as progress:
        # Left Query Execution
        task_left = progress.add_task("Executing left query...", total=1)
        left_results, left_duration = execute_sql_query(
            conn=left_conn,
            sql_query=left_query,
            params=left_params,
            show_performance=show_performance,
        )
        progress.update(task_left, completed=1)

        # Right Query Execution
        task_right = progress.add_task("Executing right query...", total=1)
        right_results, right_duration = execute_sql_query(
            conn=right_conn,
            sql_query=right_query,
            params=right_params,
            show_performance=show_performance,
        )
        progress.update(task_right, completed=1)

    result = compare_dataframes(
        QueryResult(results=left_results, duration=left_duration),
        QueryResult(results=right_results, duration=right_duration),
        case_insensitive=case_insensitive,
        show_performance=show_performance,
    )
    display_result(result)

    return result


def load_sql_file(file_path: str) -> str:
    """Load SQL query from a file"""
    sql_path = Path(file_path)

    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    with open(sql_path) as f:
        return f.read()


def run_comparisons(config: ComparisonConfig) -> bool:
    """Run all SQL comparisons from config"""
    success = True

    console.print()
    console.rule("[bold]SQL Data Comparison[/]")
    console.print("[italic]Comparing queries across database systems[/]", justify="center")
    console.print()

    # Get output settings
    output_type = config.config.get("output_type", None)
    output_dir = config.config.get("output_file_path", "./output/")
    output_format = config.config.get("output_format", "csv")
    timestamp_file = config.config.get("timestamp_file", False)
    max_sql_in_values = config.config.get("max_sql_in_values", 1000)
    show_performance = config.config.get("show_performance", True)

    for i, comparison in enumerate(config.comparisons):
        name = comparison.name
        color = COLORS[i % len(COLORS)]
        console.print()
        console.rule(f"[bold {color}]{name}[/]")

        try:
            console.print(f"Left database type:  [{color}]{comparison.left_db_type}[/]")
            console.print(f"Right database type: [{color}]{comparison.right_db_type}[/]")
            console.print()

            result = compare_sql(
                left_conn=comparison.left_connection,
                right_conn=comparison.right_connection,
                left_query=comparison.left_query,
                right_query=comparison.right_query,
                case_insensitive=comparison.case_insensitive,
                show_performance=show_performance,
            )

            # Handle output file generation if configured
            if output_type and output_dir:
                handle_output_files(
                    result=result,
                    name=name,
                    output_type=output_type,
                    output_dir=output_dir,
                    output_table_name=comparison.full_table_name,
                    output_format=output_format,
                    timestamp_file=timestamp_file,
                    max_sql_in_values=max_sql_in_values,
                )

            if not result.is_equal:
                success = False

        except Exception as e:
            success = False
            console.print(f"[bold red]Error in comparison {name}:[/] {e}")

    console.print()
    if success:
        console.rule("[bold green]All comparisons successful[/]")
    else:
        console.rule("[bold red]Some comparisons failed[/]")
    console.print()

    return success
