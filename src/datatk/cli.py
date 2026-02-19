from importlib.metadata import version

import typer

from datatk.data_cleanup.data_cleanup import main as data_cleanup_main
from datatk.data_compare.data_compare import main as data_compare_main
from datatk.db_diagram.db_diagram import main as db_diagram_main
from datatk.export_parquet.export_parquet import main as export_parquet_main
from datatk.object_compare.object_compare import main as object_compare_main
from datatk.proc_tester.proc_tester import main as proc_tester_main
from datatk.schema_size.schema_size import main as schema_size_main
from datatk.view_tester.view_tester import main as view_tester_main

app = typer.Typer(
    help="datatk (Data Toolkit) — compare, analyze, and export data across databases.",
    invoke_without_command=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"datatk {version('datatk')}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", callback=_version_callback, is_eager=True),
) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def data_compare() -> None:
    """Compare data across database platforms."""
    data_compare_main()


@app.command()
def object_compare() -> None:
    """Compare database object definitions across environments."""
    object_compare_main()


@app.command()
def schema_size() -> None:
    """Analyze storage sizes across databases."""
    schema_size_main()


@app.command()
def db_diagram() -> None:
    """Generate ERD diagrams from database metadata."""
    db_diagram_main()


@app.command()
def export_parquet() -> None:
    """Export database objects to Parquet files."""
    export_parquet_main()


@app.command()
def proc_tester() -> None:
    """Batch test stored procedures."""
    proc_tester_main()


@app.command()
def view_tester() -> None:
    """Batch test database views."""
    view_tester_main()


@app.command()
def data_cleanup() -> None:
    """Clean up data using foreign key hierarchy traversal."""
    data_cleanup_main()
