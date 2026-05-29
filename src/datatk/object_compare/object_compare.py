import hashlib
from typing import Dict, List, Set

from dotenv import load_dotenv
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..utils import DbConnection, get_config, load_connection, modify_connection_for_database
from ..utils.connection_models import DbType, parse_db_type
from ..utils.rich_utils import console
from .object_compare_fetch_objects import fetch_definitions
from .object_compare_utils import (
    ChecksumData,
    ComparisonResult,
    print_comparison_result,
    print_connection_header,
)

DISPLAY_NAMES = {
    "stored_proc": "stored procedure",
    "view": "view",
    "function": "function",
    "table": "table",
    "trigger": "trigger",
    "sequence": "sequence",
    "index": "index",
    "type": "type",
    "extension": "extension",
    "external_table": "external table",
    "foreign_key": "foreign key",
}


def build_connections(
    environments: Dict[str, str],
    db_type: DbType,
    database: str | None = None,
) -> Dict[str, DbConnection]:
    """Build a connection per environment, skipping any that fail with a warning."""
    connections: Dict[str, DbConnection] = {}
    for env_name, env_var in environments.items():
        try:
            connections[env_name] = load_connection(env_var, db_type=db_type)
            if database is not None:
                connections[env_name] = modify_connection_for_database(
                    connections[env_name], database_name=database
                )
        except ValueError as e:
            console.print(f"[yellow]Warning:[/] Failed to connect to {env_name}: {e}")
    return connections


def run_object_comparisons(
    connections: Dict[str, DbConnection],
    schema: str,
    object_types: List[str],
    db_type: str = "mssql",
) -> None:
    """Run compare_definitions for each object type, with progress messaging."""
    for obj_type in object_types:
        if obj_type in DISPLAY_NAMES:
            display_type = DISPLAY_NAMES[obj_type]
            console.print(f"\n[bold magenta]⚡ Processing {display_type}s[/]")
            compare_definitions(connections, schema, obj_type, display_type, db_type)
            console.print(f"[bold green]✓ {display_type.capitalize()}s comparison complete![/]")
        else:
            console.print(f"[yellow]Warning:[/] Unknown object type '{obj_type}' skipped")


def compare_definitions(
    connections: Dict[str, DbConnection],
    schema_name: str,
    object_type: str,
    display_name: str,
    db_type: str = "mssql",
) -> None:
    object_checksums = {}
    all_object_names: Set[str] = set()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold magenta]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"• Processing {display_name}s...", total=len(connections))

        # Fetch objects and calculate checksums for each environment
        for env, connection in connections.items():
            objects = fetch_definitions(connection, schema_name, object_type, db_type)
            all_object_names.update(objects.keys())

            # Calculate checksums
            object_checksums[env] = {
                obj_name: hashlib.md5(" ".join(definition.split()).encode("utf-8")).hexdigest()[
                    -10:
                ]
                for obj_name, definition in objects.items()
            }
            progress.advance(task)

        progress.update(
            task, description=f"  • Found {len(all_object_names)} {display_name}s. [green]Done![/]"
        )
        progress.update(task, completed=len(connections))

    # Setup table for results
    env_names = list(connections.keys())
    result = ComparisonResult(schema_name=schema_name, object_type=display_name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold magenta]{task.description}"),
        console=console,
    ) as progress:
        compare_task = progress.add_task(
            f"• Comparing {display_name}s...", total=len(all_object_names)
        )

        for obj_name in sorted(all_object_names):
            checksums = [object_checksums[env].get(obj_name, "N/A") for env in env_names]

            checksum_data = ChecksumData(
                object_name=obj_name, checksums=checksums, environments=env_names
            )

            # Only add to results if the checksums are different
            if checksum_data.has_differences():
                result.checksum_rows.append(checksum_data)

            progress.advance(compare_task)

        diff_count = len(result.checksum_rows)
        progress.update(
            compare_task, description=f"  • Found {diff_count} differences. [green]Done![/]"
        )
        progress.update(compare_task, completed=len(all_object_names))

    print_comparison_result(result)


def main() -> None:
    load_dotenv()
    object_compare_config = get_config("object_compare")
    schema = object_compare_config["schema"]
    database = object_compare_config.get("database", None)
    db_type = parse_db_type(object_compare_config.get("db_type", "mssql"))
    environments = object_compare_config.get("environments", {})
    object_types = object_compare_config.get("object_types", ["stored_proc", "view", "function"])

    connections = build_connections(environments, db_type, database)
    print_connection_header(connections, list(environments.keys()), db_type, schema)

    if not connections:
        console.print(
            "[bold red]Error:[/] No valid database connections found.",
            "Please check your environment variables and config.",
        )
        return

    run_object_comparisons(connections, schema, object_types, db_type)
    print("")


if __name__ == "__main__":
    main()
