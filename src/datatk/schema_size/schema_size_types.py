from dataclasses import dataclass, field


@dataclass
class TableSize:
    """Size metrics for a single table."""

    table_name: str
    row_count: int
    total_bytes: float
    data_bytes: float
    index_bytes: float

    @property
    def total_formatted(self) -> str:
        return format_size(self.total_bytes)

    @property
    def data_formatted(self) -> str:
        return format_size(self.data_bytes)

    @property
    def index_formatted(self) -> str:
        return format_size(self.index_bytes)


@dataclass
class SchemaSize:
    """Size metrics for a schema."""

    schema_name: str
    total_rows: int
    total_bytes: float
    data_bytes: float
    index_bytes: float
    tables: list[TableSize] | None = None  # Populated in detail mode

    @property
    def total_formatted(self) -> str:
        return format_size(self.total_bytes)

    @property
    def data_formatted(self) -> str:
        return format_size(self.data_bytes)

    @property
    def index_formatted(self) -> str:
        return format_size(self.index_bytes)


@dataclass
class DatabaseSize:
    """Aggregated size metrics for a database."""

    total_bytes: float
    data_bytes: float
    index_bytes: float
    total_rows: int = 0

    @property
    def total_formatted(self) -> str:
        return format_size(self.total_bytes)

    @property
    def data_formatted(self) -> str:
        return format_size(self.data_bytes)

    @property
    def index_formatted(self) -> str:
        return format_size(self.index_bytes)


@dataclass
class ServerResults:
    """Results for all databases on a server/environment."""

    server_name: str
    databases: dict[str, DatabaseSize] = field(default_factory=dict)

    @property
    def total_size(self) -> DatabaseSize:
        """Calculate the total size across all databases."""
        total_bytes = sum(db.total_bytes for db in self.databases.values())
        data_bytes = sum(db.data_bytes for db in self.databases.values())
        index_bytes = sum(db.index_bytes for db in self.databases.values())
        total_rows = sum(db.total_rows for db in self.databases.values())
        return DatabaseSize(total_bytes, data_bytes, index_bytes, total_rows)


def format_size(size_bytes: float, decimal_places: int = 2) -> str:
    """
    Format a size in bytes to a human-readable string with appropriate unit.

    Args:
        size_bytes: Size in bytes
        decimal_places: Number of decimal places to include

    Returns:
        Formatted string with appropriate unit (B, KB, MB, GB, TB)
    """
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0

    while size_bytes >= 1024.0 and unit_index < len(units) - 1:
        size_bytes /= 1024.0
        unit_index += 1

    return f"{size_bytes:.{decimal_places}f} {units[unit_index]}"
