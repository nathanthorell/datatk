# sql-tools

A collection of utility tools for working with various dialects of SQL databases.

## Features

- **Object Comparison Tool** (`object_compare`): Compare database object definitions across multiple environments (DEV, QA, TEST, PROD)
  - **Database Support**: MSSQL and PostgreSQL
  - **Object Types**: stored procedures, views, functions, tables, triggers, sequences, indexes, types, extensions (PostgreSQL), external tables (MSSQL), and foreign keys
  - Identify exclusive objects that exist in only one environment
  - Detect definition differences using MD5 checksums for efficient comparison
  - Rich console output with progress indicators and difference highlighting

- **Stored Procedure Tester** (`usp_tester`): Batch test execution of stored procedures with configurable parameters
  - Support for default parameter values
  - Execution time tracking
  - Different logging levels (summary, verbose)

- **View Tester** (`view_tester`): Batch test queries against views
  - Runs a "TOP 1 *" for each view to ensure output is valid
  - Execution time tracking
  - Different logging levels (summary, verbose)

- **Schema Size** (`schema_size`): Analyzes storage across databases by measuring schema sizes.
  - The tool connects to multiple servers, calculates data and index space consumption in megabytes, and generates formatted tabular reports comparing schema sizes.
  - Results are displayed with customizable detail levels based on logging preferences.

- **Data Compare** (`data_compare`): Compare data across different database platforms
  - Support for MSSQL, PostgreSQL, and Databricks databases
  - Compare data using custom SQL queries
  - Option to use query files for complex comparisons
  - Flexible output options: left_only, right_only, common, differences, or all
  - Detailed reporting on differences between datasets

- **Database Diagram Generator** (`db_diagram`): Generate ERD diagrams from database metadata
  - Support for DBML (Database Markup Language), Mermaid, and PlantUML formats
  - DBML is the default format - purpose-built for database schemas with clean, readable syntax
  - Configurable column display modes (all columns, keys only, or table names only)
  - **Hierarchical diagrams**: Focus on relationships around a specific base table with directional traversal
  - Automatic relationship detection from foreign key constraints
  - Rich console output with progress indicators and formatted results

## Installation

### Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) - Fast Python package and project manager
- Appropriate database drivers:

    - ODBC Driver for SQL Server (for MSSQL databases)
    - PostgreSQL drivers (for PostgreSQL databases)
    - Databricks SQL Connector (for Databricks, installed automatically via dependencies)

### Setup

1. Install `uv` if you haven't already:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone the repository:

   ```bash
   git clone https://github.com/nathanthorell/sql-tools.git
   cd sql-tools
   ```

3. Install dependencies with `uv` (automatically creates virtual environment):

   ```bash
   uv sync --extra dev
   ```

   Alternatively, use the Makefile:

   ```bash
   make install
   ```

4. Create a `.env` file based on the provided `.env.example`:

   ```bash
   cp .env.example .env
   ```

   Then update the connection strings with your database details.

5. Create a `config.toml` file for each tool you want to use.

## Configuration

### Environment Variables

An `.env.example` file is provided with the repository. Copy this to create your own `.env` file:

```bash
cp .env.example .env
```

Then adjust the connection strings and other settings according to your environment.

The tools will read these environment variables to establish connections to the various SQL instances.

### Tool Configurations

Create a `config.toml` file in the project root directory based on the provided `config-example.toml`:

```bash
cp config-example.toml config.toml
```

- **Object Compare**: Configure database type (MSSQL or PostgreSQL), schema name, and object types to compare across environments
- **USP Tester**: Configure the schema, logging level, and default parameter values for stored procedures
- **View Tester**: Configure the schema and logging level
- **Schema Size**: Configure the server connections, databases to compare, and logging level
- **Data Compare**: Configure named comparison pairs with left/right database connections, database types (MSSQL/PostgreSQL/Databricks), and queries or query files to compare
- **Database Diagram Generator**: Configure the connection, schema, column display mode, diagram format, and output settings

## Usage

All tools can be run using `uv run`:

### Object Comparison Tool

```bash
uv run object_compare
```

This will:

1. Connect to each configured environment using the specified connection strings
1. Query metadata for each configured object type (stored procedures, views, functions, tables, etc.)
1. Calculate MD5 checksums of object definitions for efficient comparison
1. Compare checksums across all environments to detect differences
1. Display a formatted table showing:
   - Objects that exist in some environments but not others
   - Objects with different definitions (checksum mismatches) across environments

### Stored Procedure Tester

```bash
uv run usp_tester
```

This will:

1. Connect to the configured test database
1. Execute all stored procedures in the specified schema
1. Apply default parameter values
1. Report execution status and timing

### View Tester

```bash
uv run view_tester
```

This will:

1. Connect to the configured test database
1. Execute all views in the specified schema
1. Report execution status and timing

### Schema Size

```bash
uv run schema_size
```

This will:

1. Connect to each server using the specified connection strings
1. Calculate size metrics for each database and schema
1. Generate reports showing data and index sizes per schema
1. Provide comparative summaries across all servers and databases

### Data Compare

```bash
uv run data_compare
```

1. Connect to the configured database sources (supports MSSQL, PostgreSQL, and Databricks)
1. Execute the defined queries against both data sources
1. Compare the results of both queries
1. Generate a detailed report of matching and non-matching data
1. Display performance comparison between execution time of each data source

#### Output Types

- `left_only`: Export rows that exist only in the left query result
- `right_only`: Export rows that exist only in the right query result
- `common`: Export rows that exist in both query results
- `differences`: Export both left_only and right_only (what's different)
- `all`: Export left_only, right_only, and common (complete breakdown)

### Database Diagram Generator

```bash
uv run db_diagram
```

This will:

1. Connect to the configured database using the specified connection string
1. Analyze the database schema and extract table/column metadata
1. Detect relationships based on foreign key constraints
1. Generate diagram code in the specified format (DBML, Mermaid, or PlantUML)
1. Save the diagram to the configured output directory with appropriate file extension (.dbml, .mmd, or .puml)

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
```

### Clean Up

```bash
make clean   # Remove temporary files and virtual environment
```
