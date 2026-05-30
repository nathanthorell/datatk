"""
Demo script for data_compare — runs the full comparison pipeline against
fake query results. No real DB connection required.

Run with:
    uv run python examples/data_compare_demo.py
"""

from unittest.mock import patch

import pandas as pd
from rich.console import Console
from rich.rule import Rule

from datatk.data_compare.data_compare_execute import compare_sql
from datatk.utils.connection_models import DatabricksConnection, MSSQLConnection

# ---------------------------------------------------------------------------
# Fake connections — values don't matter, execute_sql_query is patched out.
# ---------------------------------------------------------------------------

LEFT_CONN = MSSQLConnection(server="mssql-prod", database="SalesDB")
RIGHT_CONN = DatabricksConnection(
    server="adb-demo.azuredatabricks.net",
    catalog="data_warehouse",
    access_token="fake-token",
    http_path="/sql/1.0/warehouses/demo",
)

# ---------------------------------------------------------------------------
# Fake query results — represent what would come back from real DB queries.
# Left side simulates MSSQL/pyodbc, right side simulates Databricks/Arrow.
# ---------------------------------------------------------------------------

# Comparison 1: monthly sales totals — has row differences
SALES_LEFT = pd.DataFrame(
    {
        "region": ["Northeast", "Southeast", "Midwest", "Southwest", "Northwest"],
        "product_line": ["Hardware", "Hardware", "Software", "Software", "Hardware"],
        "total_sales": [142500.00, 98750.00, 210300.00, 87400.00, 165200.00],
        "order_count": [47, 31, 68, 29, 53],
    }
)

# Right side: Midwest row has a different total, Northwest is missing, West Coast is new
SALES_RIGHT = pd.DataFrame(
    {
        "region": ["Northeast", "Southeast", "Midwest", "Southwest", "West Coast"],
        "product_line": ["Hardware", "Hardware", "Software", "Software", "Hardware"],
        "total_sales": [142500.00, 98750.00, 198600.00, 87400.00, 201800.00],
        "order_count": [47, 31, 64, 29, 71],
    }
)

# Comparison 2: product inventory — equal on both sides
INVENTORY = pd.DataFrame(
    {
        "sku": ["SKU-1001", "SKU-1002", "SKU-1003", "SKU-1004"],
        "description": ["Widget A", "Widget B", "Gadget X", "Gadget Y"],
        "quantity": [500, 1200, 85, 340],
        "warehouse": ["East", "East", "West", "West"],
    }
)

# Comparison 3: region codes — same data, different string casing
REGIONS_LEFT = pd.DataFrame(
    {
        "code": ["NE", "SE", "MW", "SW", "NW"],
        "label": ["NORTHEAST", "SOUTHEAST", "MIDWEST", "SOUTHWEST", "NORTHWEST"],
        "active": [True, True, True, False, True],
    }
)

REGIONS_RIGHT = pd.DataFrame(
    {
        "code": ["NE", "SE", "MW", "SW", "NW"],
        "label": ["Northeast", "Southeast", "Midwest", "Southwest", "Northwest"],
        "active": [True, True, True, False, True],
    }
)


# ---------------------------------------------------------------------------
# Fake execute — returns canned results keyed by connection identity.
# ---------------------------------------------------------------------------

LEFT_RESULTS = {
    "SELECT * FROM monthly_sales": (SALES_LEFT, 1.42),
    "SELECT * FROM inventory": (INVENTORY, 0.63),
    "SELECT * FROM region_codes": (REGIONS_LEFT, 0.21),
}

RIGHT_RESULTS = {
    "SELECT * FROM monthly_sales": (SALES_RIGHT, 0.87),
    "SELECT * FROM inventory": (INVENTORY.copy(), 0.41),
    "SELECT * FROM region_codes": (REGIONS_RIGHT, 0.18),
}


def _fake_execute(
    conn: object, sql_query: str, params: object = None, show_performance: bool = True
) -> tuple[pd.DataFrame, float]:
    results = LEFT_RESULTS if conn is LEFT_CONN else RIGHT_RESULTS
    return results[sql_query]


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------


def run_demo(save_svg: bool = False) -> None:
    recording = Console(record=True)

    with (
        patch("datatk.data_compare.data_compare_execute.console", recording),
        patch("datatk.data_compare.data_compare_output.console", recording),
        patch(
            "datatk.data_compare.data_compare_execute.execute_sql_query", side_effect=_fake_execute
        ),
    ):
        recording.print(Rule("[bold]data_compare demo[/]"))
        recording.print(
            "[italic]Comparing query results across MSSQL and Databricks[/]",
            justify="center",
        )

        # --- Comparison 1: sales totals (has differences) ---
        recording.print(Rule("[bold cyan]Monthly Sales Totals[/]"))
        recording.print("Left database type:  [cyan]mssql[/]")
        recording.print("Right database type: [cyan]databricks[/]")
        recording.print()
        compare_sql(
            LEFT_CONN,
            RIGHT_CONN,
            "SELECT * FROM monthly_sales",
            "SELECT * FROM monthly_sales",
            show_performance=False,
        )

        # --- Comparison 2: inventory (equal) ---
        recording.print(Rule("[bold green]Product Inventory[/]"))
        recording.print("Left database type:  [green]mssql[/]")
        recording.print("Right database type: [green]databricks[/]")
        recording.print()
        compare_sql(
            LEFT_CONN,
            RIGHT_CONN,
            "SELECT * FROM inventory",
            "SELECT * FROM inventory",
            show_performance=False,
        )

        # --- Comparison 3: region codes (case-insensitive match) ---
        recording.print(Rule("[bold yellow]Region Codes — case-insensitive[/]"))
        recording.print("Left database type:  [yellow]mssql[/]")
        recording.print("Right database type: [yellow]databricks[/]")
        recording.print()
        compare_sql(
            LEFT_CONN,
            RIGHT_CONN,
            "SELECT * FROM region_codes",
            "SELECT * FROM region_codes",
            case_insensitive=True,
            show_performance=False,
        )

    if save_svg:
        svg_path = "examples/data_compare_demo.svg"
        recording.save_svg(svg_path, title="data_compare demo")
        print(f"SVG saved to {svg_path}")


if __name__ == "__main__":
    import sys

    run_demo(save_svg="--save-svg" in sys.argv)
