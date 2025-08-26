import argparse
import os
from textwrap import dedent
from typing import cast

import pyodbc

from dolly.internal import secrets
from dolly.state import get_table_hashes, set_table_hash

# Set environment to prod to pull from firestore and get correct secrets
os.environ["APP_ENVIRONMENT"] = "prod"
os.environ.pop("FIRESTORE_EMULATOR_HOST", None)

LAST_CHECKED = "2025-08-21"
host = secrets["INTERNAL_HOST"]
database = secrets["INTERNAL_DATABASE"]
username = secrets["INTERNAL_USERNAME"]
password = secrets["INTERNAL_PASSWORD"]

CONNECTION_STRING = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={host};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    f"TrustServerCertificate=yes;"
)


def _get_database_connection() -> pyodbc.Connection:
    """
    Factory function to create a database connection.

    Returns:
        pyodbc.Connection: Database connection object
    """

    return pyodbc.connect(CONNECTION_STRING)


def get_current_hashes(updated_before: str | None = None) -> dict[str, str]:
    """Retrieve current hashes for all tables from ChangeDetection.

    Args:
        updated_before: Optional date string to filter results.

    Returns:
        Mapping of table name (lower-case) -> hash string.
    """

    query = "SELECT table_name, hash FROM SGID.META.ChangeDetection"
    if updated_before:
        query += f" WHERE last_modified <= '{updated_before}'"

    connection = _get_database_connection()

    try:
        cursor = cast(pyodbc.Connection, connection).cursor()
        cursor.execute(dedent(query))
        rows = cursor.fetchall()
        cursor.close()
        return {row[0].lower(): str(row[1]) for row in rows}
    finally:
        connection.close()


def write_hashes_to_firestore(hashes: dict[str, str]):
    """Write all SGID hashes to Firestore, overwriting existing values.

    Args:
        hashes: A dictionary of table names and their hashes.
    """
    print(f"Writing {len(hashes)} hashes to Firestore...")
    for table, hash_value in hashes.items():
        set_table_hash(table, hash_value)
    print("Done writing to Firestore.")


def main():
    """
    Queries the change detection table and firestore for hashes and prints the differences.
    """
    parser = argparse.ArgumentParser(
        description="Compare SGID and Firestore hashes, with an option to write them."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the SGID hashes to Firestore.",
    )
    args = parser.parse_args()

    print("Getting current hashes from SGID...")
    sgid_hashes = get_current_hashes(LAST_CHECKED)
    print(f"Found {len(sgid_hashes)} hashes in SGID.")

    if args.write:
        write_hashes_to_firestore(sgid_hashes)
        return

    print("Getting stored hashes from Firestore...")
    firestore_hashes = get_table_hashes()
    print(f"Found {len(firestore_hashes)} hashes in Firestore.")

    new_tables = []
    updated_tables = []
    unchanged_tables = []

    for table, sgid_hash in sgid_hashes.items():
        if table not in firestore_hashes:
            new_tables.append(table)
        elif firestore_hashes[table] != sgid_hash:
            updated_tables.append((table, sgid_hash, firestore_hashes[table]))
        else:
            unchanged_tables.append(table)

    print("\n--- Comparison Results ---")

    if new_tables:
        print(f"\n{len(new_tables)} New tables (in SGID but not Firestore):")
        for table in sorted(new_tables):
            print(f"  - {table}")

    if updated_tables:
        print(f"\n{len(updated_tables)} Updated tables (hashes differ):")
        for table, sgid_hash, firestore_hash in sorted(updated_tables):
            print(f"  - {table}:")
            print(f"    SGID:      {sgid_hash}")
            print(f"    Firestore: {firestore_hash}")

    if unchanged_tables:
        print(f"\n{len(unchanged_tables)} tables are unchanged.")

    print("\n--- End of Report ---")


if __name__ == "__main__":
    main()
