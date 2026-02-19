import time
from datetime import date, datetime
from typing import Any, Dict, List, Union

from dotenv import load_dotenv

from ..utils import Connection, get_config, load_connection, modify_connection_for_database
from ..utils.rich_utils import align_columns, console, create_table


def get_default_for_date_type(
    param_name: str, date_defaults: Dict[str, Union[date, datetime]]
) -> Union[date, datetime]:
    """
    Returns the appropriate default for date or datetime parameters based on the parameter name.
    :param param_name: The name of the parameter (e.g., 'start_date', 'end_date').
    :param date_defaults: A dictionary containing default values for date and datetime types.
    :return: The default value for the parameter.
    """
    param_name_lower = param_name.lower()

    if "start" in param_name_lower:
        if "datetime" in param_name_lower:
            return date_defaults["start_datetime"]
        return date_defaults["start_date"]
    elif "end" in param_name_lower:
        if "datetime" in param_name_lower:
            return date_defaults["end_datetime"]
        return date_defaults["end_date"]
    else:
        return date_defaults["start_date"]


def execute_procedure(
    conn: Connection,
    schema: str,
    proc_name: str,
    defaults: Dict[str, Any],
    logging_level: str,
) -> Dict[str, Any]:
    """
    Execute a single stored procedure with the given parameters.

    :param conn: The database connection object.
    :param schema: The schema name for the stored procedure.
    :param proc_name: The name of the stored procedure.
    :param defaults: A dictionary containing default values for parameter types.
    :param logging_level: Expects a string value ("verbose", "errors_only", or "summary").
    """

    with conn.connect() as db_conn:
        cursor = db_conn.cursor()
        try:
            # Fetch parameters for the stored procedure
            param_query = f"""
            SELECT PARAMETER_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.PARAMETERS
            WHERE SPECIFIC_SCHEMA = '{schema}' AND SPECIFIC_NAME = '{proc_name}'
            """
            cursor.execute(param_query)
            parameters = cursor.fetchall()

            # Prepare default mapping for non-date types
            default_map = {
                "int": defaults["integer"],
                "bit": defaults["bit"],
                "decimal": defaults["decimal"],
                "varchar": defaults["varchar"],
                "nvarchar": defaults["varchar"],
            }

            proc_args: list[Any] = []
            for param in parameters:
                param_name, param_type = param

                # Check for date or datetime types based on name and type
                if param_type in ["date", "datetime", "smalldatetime"]:
                    proc_args.append(get_default_for_date_type(param_name, defaults))
                else:
                    # Use the default mapping for other types
                    proc_args.append(
                        default_map.get(param_type, None)
                    )  # Fallback to None if type isn't mapped

            # Build the EXEC query with f-strings for the procedure name and placeholders
            placeholder_str = ", ".join(
                [f"'{arg}'" if arg is not None else "NULL" for arg in proc_args]
            )
            exec_query = f"EXEC [{schema}].[{proc_name}] {placeholder_str}"

            start_time = time.time()

            if logging_level == "verbose":
                console.print(f"Running: {exec_query}")

            cursor.execute(exec_query)

            end_time = time.time()
            elapsed_time = end_time - start_time

            if logging_level == "verbose":
                console.print(f"Executed with arguments: {proc_args} in {elapsed_time:.2f} seconds")

            return {
                "proc_name": proc_name,
                "status": "success",
                "elapsed_time": elapsed_time,
            }

        except Exception as e:
            if logging_level in ["verbose", "errors_only"]:
                console.print(f"[bold red]Error executing[/] [bold]{proc_name}[/]: {e}")

            return {
                "proc_name": proc_name,
                "status": "fail",
                "elapsed_time": None,
                "error_message": str(e),
            }


def print_results_summary(results: List[Dict[str, Any]], logging_level: str) -> None:
    if logging_level == "summary":
        console.print()
        table = create_table(columns=["Procedure Name", "Status", "Time", "Error"])
        align_columns(table, {"Time": "right"})

        for result in results:
            proc_name = result["proc_name"]
            status = result["status"]
            elapsed_time = f"{result['elapsed_time']:.2f}s" if result["elapsed_time"] else "N/A"
            error_msg = result.get("error_message", "") or ""

            status_styled = f"[green]{status}[/]" if status == "success" else f"[red]{status}[/]"
            table.add_row(proc_name, status_styled, elapsed_time, error_msg)

        console.print(table)

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = len(results) - success_count
        console.print(
            f"\nTotal: {len(results)} procedures | "
            f"[green]Success: {success_count}[/] | "
            f"[red]Errors: {error_count}[/]"
        )

    elif logging_level == "errors_only":
        error_results = [r for r in results if r["status"] == "fail"]

        if not error_results:
            console.print("[green]No errors found.[/]")
            return

        console.print()
        table = create_table(columns=["Procedure Name", "Time", "Error"])
        align_columns(table, {"Time": "right"})

        for result in error_results:
            proc_name = result["proc_name"]
            elapsed_time = f"{result['elapsed_time']:.2f}s" if result["elapsed_time"] else "N/A"
            error_msg = result.get("error_message", "") or ""
            table.add_row(proc_name, elapsed_time, error_msg)

        console.print(table)
        console.print(
            f"\n[red]Found {len(error_results)} errors[/] out of {len(results)} procedures."
        )


def main() -> None:
    load_dotenv()
    usp_config = get_config("proc_tester")

    defaults = usp_config["defaults"]
    schema = usp_config["schema"]
    logging_level = usp_config["logging_level"]

    # Get connection from config
    conn_env_var = usp_config.get("conn")
    if not conn_env_var:
        raise ValueError("Connection variable 'conn' not defined in config")

    connection = load_connection(conn_env_var)

    # Optionally switch to a different database
    database = usp_config.get("database")
    if database:
        connection = modify_connection_for_database(connection, database)

    console.print()
    console.rule("[bold cyan]Stored Procedure Tester[/]")
    console.print(
        f"Server: [bold]{connection.server}[/] | "
        f"Database: [bold]{connection.database}[/] | "
        f"Schema: [bold]{schema}[/]"
    )
    console.print(f"Logging level: [italic]{logging_level}[/]")
    console.print()

    stored_procedures: List[str] = []

    try:
        with connection.connect() as db_conn:
            cursor = db_conn.cursor()
            query = f"""
            SELECT SPECIFIC_NAME
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_TYPE = 'PROCEDURE'
            AND ROUTINE_SCHEMA = '{schema}'
            ORDER BY SPECIFIC_NAME;
            """
            cursor.execute(query)
            stored_procedures = [proc[0] for proc in cursor.fetchall()]

        if not stored_procedures:
            console.print(f"[yellow]No stored procedures found in schema '{schema}'[/]")
            return

        console.print(f"Found [bold]{len(stored_procedures)}[/] stored procedures to test\n")

        results: List[Dict[str, Any]] = []
        for proc_name in stored_procedures:
            if logging_level == "verbose":
                console.print(f"Executing stored procedure: [bold]{proc_name}[/]")

            result = execute_procedure(connection, schema, proc_name, defaults, logging_level)
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
