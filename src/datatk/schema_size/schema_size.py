"""Schema size analysis tool for analyzing database storage metrics."""

from ..utils import get_config, load_connection
from ..utils.config_models import SchemaSizeConfig
from ..utils.rich_utils import align_columns, console, create_table
from .schema_size_types import (
    SchemaSize,
    ServerResults,
)
from .schema_size_utils import (
    process_environment_detail,
    process_environment_summary,
)


def print_summary_tables(env_results: dict[str, ServerResults]) -> None:
    """Print summary tables for all environments."""
    # Database-level summary table
    summary_table = create_table(
        columns=["Environment", "Database", "Row Count", "Total Size", "Data Size", "Index Size"]
    )

    align_columns(
        summary_table,
        {
            "Row Count": "right",
            "Total Size": "right",
            "Data Size": "right",
            "Index Size": "right",
        },
    )

    # Environment totals table
    totals_table = create_table(
        columns=["Environment", "Row Count", "Total Size", "Data Size", "Index Size"]
    )

    align_columns(
        totals_table,
        {
            "Row Count": "right",
            "Total Size": "right",
            "Data Size": "right",
            "Index Size": "right",
        },
    )

    for env_name, results in env_results.items():
        for db_name, db_size in results.databases.items():
            summary_table.add_row(
                env_name,
                db_name,
                f"{db_size.total_rows:,}",
                db_size.total_formatted,
                db_size.data_formatted,
                db_size.index_formatted,
            )

        env_total = results.total_size
        totals_table.add_row(
            env_name,
            f"{env_total.total_rows:,}",
            env_total.total_formatted,
            env_total.data_formatted,
            env_total.index_formatted,
        )

    console.print("\nDatabase Size Summary:")
    console.print(summary_table)
    console.print("\nEnvironment Totals:")
    console.print(totals_table)


def print_detail_tables(
    env_name: str,
    db_results: dict[str, list[SchemaSize]],
    sort_by: str,
    top_n: int,
) -> None:
    """Print detailed table-level breakdown for an environment."""
    for db_name, schemas in db_results.items():
        console.print(f"\n[bold]Table Details for [{env_name}].[{db_name}][/]")
        console.print(f"[dim]Sorted by: {sort_by}, Top {top_n} per schema[/]\n")

        for schema in schemas:
            if not schema.tables:
                continue

            console.print(f"[cyan]Schema: {schema.schema_name}[/]")
            console.print(
                f"[dim]Total: {schema.total_formatted} "
                f"(Data: {schema.data_formatted}, Index: {schema.index_formatted}, "
                f"Rows: {schema.total_rows:,})[/]\n"
            )

            table = create_table(
                columns=["Table", "Row Count", "Total Size", "Data Size", "Index Size"]
            )

            align_columns(
                table,
                {
                    "Row Count": "right",
                    "Total Size": "right",
                    "Data Size": "right",
                    "Index Size": "right",
                },
            )

            for tbl in schema.tables:
                table.add_row(
                    tbl.table_name,
                    f"{tbl.row_count:,}",
                    tbl.total_formatted,
                    tbl.data_formatted,
                    tbl.index_formatted,
                )

            console.print(table)
            console.print()


def run_summary_mode(config: SchemaSizeConfig) -> None:
    """Run the tool in summary mode, showing schema-level aggregates."""
    logging_level = config.logging_level or "summary"

    env_results: dict[str, ServerResults] = {}

    for env in config.environments:
        connection = load_connection(env.conn)
        results = process_environment_summary(env, connection, config.db_type, logging_level)
        env_results[env.name] = results

    print_summary_tables(env_results)


def run_detail_mode(config: SchemaSizeConfig) -> None:
    """Run the tool in detail mode, showing table-level breakdown."""
    for env in config.environments:
        connection = load_connection(env.conn)
        db_results = process_environment_detail(
            env, connection, config.db_type, config.sort_by, config.top_n
        )
        print_detail_tables(env.name, db_results, config.sort_by, config.top_n)


def main() -> None:
    """Main entry point for schema size analysis tool."""
    raw_config = get_config("schema_size")
    config = SchemaSizeConfig(**raw_config)

    console.print()
    console.rule("[bold cyan]SQL Schema Size Analysis[/]")
    console.print("[italic]Analyzing database and schema storage metrics[/]", justify="center")
    console.print()

    console.print(f"Mode: [bold]{config.mode}[/] | DB Type: [bold]{config.db_type}[/]")
    console.print(f"Environments: [bold]{len(config.environments)}[/]")
    for env in config.environments:
        schema_info = f", schemas: {env.schemas}" if env.schemas else ""
        console.print(f"  [green]{env.name}[/] - {len(env.databases)} databases{schema_info}")
    console.print()

    if config.mode == "detail":
        console.print(
            f"Detail options: sort_by=[bold]{config.sort_by}[/], top_n=[bold]{config.top_n}[/]"
        )
        console.print()
        run_detail_mode(config)
    else:
        run_summary_mode(config)

    console.print()
    console.rule("[bold cyan]Analysis Complete[/]")
    console.print()


if __name__ == "__main__":
    main()
