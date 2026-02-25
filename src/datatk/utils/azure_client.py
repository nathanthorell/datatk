"""Azure credential and service utilities."""

import struct

import pyodbc
from azure.identity import DefaultAzureCredential


class AzureClient:
    """Azure client with improved credential handling and service operations

    Uses DefaultAzureCredential, which resolves credentials in this order:
      1. Environment variables
      2. Workload / managed identity
      3. Azure CLI (az login) — cached, no browser popup
      4. Azure Developer CLI, VS Code, etc.
      5. Interactive browser (fallback — opens once, token cached by MSAL)
    """

    # pyodbc connection attribute for pre-auth access token (SQL Server ODBC driver)
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    SQL_SCOPE = "https://database.windows.net/.default"

    def __init__(self) -> None:
        self._credential = DefaultAzureCredential()

    def get_sql_token_struct(self) -> bytes:
        """Get a SQL Server access token formatted for pyodbc.

        pyodbc expects the token as a UTF-16-LE encoded byte string
        prefixed with its length as a 4-byte little-endian integer
        """
        token = self._credential.get_token(self.SQL_SCOPE)
        encoded = token.token.encode("UTF-16-LE")
        return struct.pack(f"<I{len(encoded)}s", len(encoded), encoded)

    def get_pyodbc_connection(self, connection_string: str) -> pyodbc.Connection:
        """Get a pyodbc connection authenticated via Azure AD token"""
        token = self.get_sql_token_struct()
        return pyodbc.connect(
            connection_string,
            attrs_before={self.SQL_COPT_SS_ACCESS_TOKEN: token},
        )
