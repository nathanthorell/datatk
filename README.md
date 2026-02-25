# datatk — Data Toolkit

A CLI toolkit for comparing, analyzing, and exporting data across databases and file formats.

Supports MSSQL, PostgreSQL, Databricks, and Parquet.

## Installation

```bash
pip install datatk
# or
uv tool install datatk
```

### From Source

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/nathanthorell/datatk.git
cd datatk
uv sync --extra dev
```

## Quick Start

```bash
datatk --help
datatk data-compare
datatk object-compare
datatk schema-size
datatk db-diagram
datatk export-parquet
datatk proc-tester
datatk view-tester
datatk data-cleanup
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and update the connection strings for your databases:

```bash
cp .env.example .env
```

Connection string formats:

- **MSSQL**: `Server=host,port;Database=db;UID=user;PWD=pass`
- **MSSQL (Azure AD interactive)**: `Server=host,port;Database=db;Authentication=ActiveDirectoryInteractive` (opens browser for Entra ID login; `UID` is optional as a login hint)
- **PostgreSQL**: `postgresql://user:pass@host:port/database`
- **Databricks**: `databricks://token:ACCESS_TOKEN@host/catalog?http_path=/sql/1.0/warehouses/ID`

### Tool Configuration

Copy `config-example.toml` to `config.toml` and configure the tools you want to use:

```bash
cp config-example.toml config.toml
```

The `[datatk]` section sets global defaults (e.g. `logging_level`) that apply to all tools unless
overridden in a tool-specific section.

## Tools

### `data-compare`

Compare data across different database platforms.

```bash
datatk data-compare
```

- Supports MSSQL, PostgreSQL, and Databricks
- Compare data using inline SQL or query files
- Output options: `left_only`, `right_only`, `common`, `differences`, or `all`
- Optional case-insensitive string comparison (`case_insensitive`), configurable globally or per comparison
- Reports differences and execution time per source (suppress with `show_performance = false`)

### `object-compare`

Compare database object definitions across environments (DEV, QA, TEST, PROD).

```bash
datatk object-compare
```

- Supports MSSQL and PostgreSQL
- Object types: stored procedures, views, functions, tables, triggers, sequences, indexes,
  types, extensions (PostgreSQL), external tables (MSSQL), and foreign keys
- Detects objects that exist in only some environments
- Uses MD5 checksums for efficient definition comparison

### `schema-size`

Analyze storage across databases by measuring schema sizes.

```bash
datatk schema-size
```

- Connects to multiple servers and calculates data and index space in megabytes
- Summary and detail modes
- Comparative reports across servers and databases

### `db-diagram`

Generate ERD diagrams from database metadata.

```bash
datatk db-diagram
```

- Output formats: DBML (default), Mermaid, PlantUML
- Column display modes: all columns, keys only, or table names only
- Hierarchical mode: focus on relationships around a specific base table with
  directional traversal (up, down, or both)
- Detects relationships from foreign key constraints

### `export-parquet`

Export database objects to Parquet files.

```bash
datatk export-parquet
```

- Connects to MSSQL databases and exports tables or query results
- Configurable batch size
- Tracks export timing per object

### `proc-tester`

Batch test stored procedures with configurable default parameters.

```bash
datatk proc-tester
```

- Executes all stored procedures in a configured schema
- Applies default values for common parameter types
- Reports execution status and timing

### `view-tester`

Batch test database views.

```bash
datatk view-tester
```

- Runs a `SELECT TOP 1 *` against each view in a configured schema
- Reports execution status and timing

### `data-cleanup`

Delete data using foreign key hierarchy traversal to handle dependencies automatically.

```bash
datatk data-cleanup
```

- Traverses foreign key relationships to determine deletion order
- Summary and execute modes (run summary first to preview)
- Configurable batch size and threshold

## Development

### Linting and Formatting

```bash
uv run ruff check src/        # Run ruff linter
uv run ruff check src/ --fix  # Run ruff with auto-fix
uv run mypy src/              # Run mypy type checker
uv run ruff format src/       # Format code with ruff
```

Or use the Makefile:

```bash
make lint    # Run ruff and mypy linters
make format  # Format code with ruff
make clean   # Remove temporary files and virtual environment
```
