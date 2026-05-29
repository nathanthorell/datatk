"""
Demo script for object_compare — runs the full tool pipeline against
fake database object definitions. No real DB connection required.

Run with:
    uv run python examples/object_compare_demo.py
"""

from unittest.mock import patch

from rich.console import Console

from datatk.object_compare.object_compare import run_object_comparisons
from datatk.object_compare.object_compare_utils import print_connection_header
from datatk.utils import DbConnection
from datatk.utils.connection_models import MSSQLConnection

# ---------------------------------------------------------------------------
# Fake object definitions — these represent what fetch_definitions() would
# return from a real database query. Maps object_name -> definition.
# ---------------------------------------------------------------------------

STORED_PROCS = {
    "dev": {
        "usp_GetOrders": (
            "CREATE PROCEDURE dbo.usp_GetOrders @CustomerId INT AS "
            "SELECT OrderId, OrderDate, TotalAmount FROM dbo.Orders "
            "WHERE CustomerId = @CustomerId"
        ),
        "usp_GetCustomers": (
            "CREATE PROCEDURE dbo.usp_GetCustomers @ActiveOnly BIT = 1 AS "
            "SELECT CustomerId, FirstName, LastName, Email FROM dbo.Customers "
            "WHERE (@ActiveOnly = 0 OR IsActive = 1)"
        ),
        "usp_ArchiveOldOrders": (
            "CREATE PROCEDURE dbo.usp_ArchiveOldOrders @CutoffDate DATE AS "
            "INSERT INTO dbo.OrdersArchive SELECT * FROM dbo.Orders "
            "WHERE OrderDate < @CutoffDate "
            "DELETE FROM dbo.Orders WHERE OrderDate < @CutoffDate"
        ),
    },
    "test": {
        "usp_GetOrders": (
            "CREATE PROCEDURE dbo.usp_GetOrders @CustomerId INT AS "
            "SELECT OrderId, OrderDate, TotalAmount FROM dbo.Orders "
            "WHERE CustomerId = @CustomerId"
        ),
        # usp_GetCustomers has an extra column in test
        "usp_GetCustomers": (
            "CREATE PROCEDURE dbo.usp_GetCustomers @ActiveOnly BIT = 1 AS "
            "SELECT CustomerId, FirstName, LastName, Email, PhoneNumber FROM dbo.Customers "
            "WHERE (@ActiveOnly = 0 OR IsActive = 1)"
        ),
        # usp_ArchiveOldOrders is missing in test
    },
    "prod": {
        "usp_GetOrders": (
            "CREATE PROCEDURE dbo.usp_GetOrders @CustomerId INT AS "
            "SELECT OrderId, OrderDate, TotalAmount FROM dbo.Orders "
            "WHERE CustomerId = @CustomerId"
        ),
        "usp_GetCustomers": (
            "CREATE PROCEDURE dbo.usp_GetCustomers @ActiveOnly BIT = 1 AS "
            "SELECT CustomerId, FirstName, LastName, Email FROM dbo.Customers "
            "WHERE (@ActiveOnly = 0 OR IsActive = 1)"
        ),
        # usp_ArchiveOldOrders is missing in prod
    },
}

VIEWS = {
    "dev": {
        "vw_ActiveCustomers": (
            "CREATE VIEW dbo.vw_ActiveCustomers AS "
            "SELECT CustomerId, FirstName, LastName, Email FROM dbo.Customers "
            "WHERE IsActive = 1"
        ),
        "vw_OrderSummary": (
            "CREATE VIEW dbo.vw_OrderSummary AS "
            "SELECT c.CustomerId, c.FirstName, COUNT(o.OrderId) AS OrderCount "
            "FROM dbo.Customers c LEFT JOIN dbo.Orders o ON c.CustomerId = o.CustomerId "
            "GROUP BY c.CustomerId, c.FirstName"
        ),
    },
    "test": {
        "vw_ActiveCustomers": (
            "CREATE VIEW dbo.vw_ActiveCustomers AS "
            "SELECT CustomerId, FirstName, LastName, Email FROM dbo.Customers "
            "WHERE IsActive = 1"
        ),
        "vw_OrderSummary": (
            "CREATE VIEW dbo.vw_OrderSummary AS "
            "SELECT c.CustomerId, c.FirstName, COUNT(o.OrderId) AS OrderCount "
            "FROM dbo.Customers c LEFT JOIN dbo.Orders o ON c.CustomerId = o.CustomerId "
            "GROUP BY c.CustomerId, c.FirstName"
        ),
    },
    "prod": {
        "vw_ActiveCustomers": (
            "CREATE VIEW dbo.vw_ActiveCustomers AS "
            "SELECT CustomerId, FirstName, LastName, Email FROM dbo.Customers "
            "WHERE IsActive = 1"
        ),
        # vw_OrderSummary different in prod — no FirstName
        "vw_OrderSummary": (
            "CREATE VIEW dbo.vw_OrderSummary AS "
            "SELECT c.CustomerId, COUNT(o.OrderId) AS OrderCount "
            "FROM dbo.Customers c LEFT JOIN dbo.Orders o ON c.CustomerId = o.CustomerId "
            "GROUP BY c.CustomerId"
        ),
    },
}

ALL_DEFINITIONS = {
    "stored_proc": STORED_PROCS,
    "view": VIEWS,
}

CONNECTIONS: dict[str, DbConnection] = {
    "dev": MSSQLConnection(server="dev-sql-01", database="AppDB"),
    "test": MSSQLConnection(server="test-sql-01", database="AppDB"),
    "prod": MSSQLConnection(server="prod-sql-01", database="AppDB"),
}

# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------


def _fake_fetch(
    conn: object, schema_name: str, object_type: str, db_type: str = "mssql"
) -> dict[str, str]:
    """Serves canned definitions keyed by object_type then environment."""
    env_defs = ALL_DEFINITIONS.get(object_type, {})
    for env, fake_conn in CONNECTIONS.items():
        if conn is fake_conn:
            return env_defs.get(env, {})
    return {}


def run_demo(save_svg: bool = False) -> None:
    recording = Console(record=True)

    with (
        patch("datatk.object_compare.object_compare.console", recording),
        patch("datatk.object_compare.object_compare_utils.console", recording),
        patch("datatk.object_compare.object_compare.fetch_definitions", side_effect=_fake_fetch),
    ):
        print_connection_header(
            connections=CONNECTIONS,
            environment_names=list(CONNECTIONS.keys()),
            db_type="mssql",
            schema="dbo",
        )
        run_object_comparisons(CONNECTIONS, "dbo", list(ALL_DEFINITIONS.keys()))

    if save_svg:
        svg_path = "examples/object_compare_demo.svg"
        recording.save_svg(svg_path, title="object_compare demo")
        print(f"SVG saved to {svg_path}")


if __name__ == "__main__":
    import sys

    run_demo(save_svg="--save-svg" in sys.argv)
