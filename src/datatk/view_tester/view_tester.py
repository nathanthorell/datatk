import re
import time
from typing import Any, Dict, List

from dotenv import load_dotenv

from ..utils import DbConnection, get_config, load_connection, modify_connection_for_database
from ..utils.rich_utils import align_columns, console, create_table


def fetch_views(conn: DbConnection, schema: str) -> List[str]:
    query = f"""
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.VIEWS
    WHERE TABLE_SCHEMA = '{schema}'
    ORDER BY TABLE_NAME;
    """
    with conn.connect() as db_conn:
        cursor = db_conn.cursor()
        try:
            cursor = db_conn.cursor()
            cursor.execute(query)
            views = cursor.fetchall()

            return [view[0] for view in views]
        except Exception as e:
            console.print(f"[bold red]Error fetching views:[/] {e}")
            return []


def execute_view(
    conn: DbConnection, schema: str, view_name: str, logging_level: str
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "view_name": view_name,
        "status": "Success",
        "elapsed_time": None,
        "error_message": None,
    }

    with conn.connect() as db_conn:
        cursor = db_conn.cursor()
        try:
            start_time = time.time()

            query = f"SELECT TOP 1 * FROM [{schema}].[{view_name}]"
            cursor.execute(query)
            cursor.fetchone()

            end_time = time.time()
            result["elapsed_time"] = end_time - start_time

            if logging_level == "verbose":
                console.print(f"[green]Successfully queried view[/] [bold]{view_name}[/]")
                console.print(f"Execution time: {result['elapsed_time']:.2f} seconds")

        except Exception as e:
            result["status"] = "Error"
            error_str = str(e)

            # Look for typical SQL Server error pattern
            if "SQLServer" in error_str or "SQL Server" in error_str:
                # Try to extract the most meaningful part of the error message
                if "Invalid column name" in error_str:
                    # Extract the column name from the error
                    column_match = re.search(r"Invalid column name '([^']+)'", error_str)
                    if column_match:
                        result["error_message"] = f"Invalid column name '{column_match.group(1)}'"
                    else:
                        result["error_message"] = "Invalid column name in view"
                else:
                    # General extraction for other SQL Server errors
                    # Find the most relevant part of the message
                    parts = error_str.split("]")
                    if len(parts) > 2:  # We have parts like [SQLServer][Driver][SQL Server]Message
                        # The relevant message is usually after the last bracket
                        msg_part = parts[-1].split("(")[0].strip()
                        result["error_message"] = msg_part
                    else:
                        result["error_message"] = error_str
            else:
                # For other types of errors
                result["error_message"] = error_str

            if logging_level == "verbose":
                console.print(
                    f"[bold red]Error executing view[/] [bold]{view_name}[/]: {error_str}"
                )

    return result


def print_results_summary(results: List[Dict[str, Any]], logging_level: str) -> None:
    if logging_level == "summary":
        console.print()
        table = create_table(columns=["View Name", "Status", "Time", "Error"])
        align_columns(table, {"Time": "right"})

        for result in results:
            view_name = result["view_name"]
            status = result["status"]
            elapsed_time = f"{result['elapsed_time']:.2f}s" if result["elapsed_time"] else "N/A"
            error_msg = result.get("error_message", "") or ""

            status_styled = f"[green]{status}[/]" if status == "Success" else f"[red]{status}[/]"
            table.add_row(view_name, status_styled, elapsed_time, error_msg)

        console.print(table)

        success_count = sum(1 for r in results if r["status"] == "Success")
        error_count = len(results) - success_count
        console.print(
            f"\nTotal: {len(results)} views | "
            f"[green]Success: {success_count}[/] | "
            f"[red]Errors: {error_count}[/]"
        )

    elif logging_level == "errors_only":
        error_results = [r for r in results if r["status"] == "Error"]

        if not error_results:
            console.print("[green]No errors found.[/]")
            return

        console.print()
        table = create_table(columns=["View Name", "Time", "Error"])
        align_columns(table, {"Time": "right"})

        for result in error_results:
            view_name = result["view_name"]
            elapsed_time = f"{result['elapsed_time']:.2f}s" if result["elapsed_time"] else "N/A"
            error_msg = result.get("error_message", "") or ""
            table.add_row(view_name, elapsed_time, error_msg)

        console.print(table)
        console.print(f"\n[red]Found {len(error_results)} errors[/] out of {len(results)} views.")


def main() -> None:
    load_dotenv()
    view_config = get_config("view_tester")
    schema = view_config["schema"]
    logging_level = view_config["logging_level"]

    # Get connection from config
    conn_env_var = view_config.get("conn")
    if not conn_env_var:
        raise ValueError("Connection variable 'conn' not defined in config")

    connection = load_connection(conn_env_var)

    # Optionally switch to a different database
    database = view_config.get("database")
    if database:
        connection = modify_connection_for_database(connection, database)

    console.print()
    console.rule("[bold cyan]View Tester[/]")
    console.print(
        f"Server: [bold]{connection.server}[/] | "
        f"Database: [bold]{connection.database}[/] | "
        f"Schema: [bold]{schema}[/]"
    )
    console.print(f"Logging level: [italic]{logging_level}[/]")
    console.print()

    try:
        views = fetch_views(connection, schema)

        if not views:
            console.print(f"[yellow]No views found in schema '{schema}'[/]")
            return

        console.print(f"Found [bold]{len(views)}[/] views to test\n")

        results: List[Dict[str, Any]] = []
        for view_name in views:
            if logging_level == "verbose":
                console.print(f"Querying view: [bold]{view_name}[/]")

            result = execute_view(connection, schema, view_name, logging_level)
            results.append(result)

            if logging_level == "verbose":
                console.print()

        print_results_summary(results, logging_level)

    except Exception as ex:
        console.print(f"[bold red]Database error:[/] {ex}")

    console.print()
    console.rule("[bold cyan]Complete[/]")
    console.print()


if __name__ == "__main__":
    main()
