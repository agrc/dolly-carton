#!/usr/bin/env python3
"""
Dolly script for pulling data from SGID Internal and pushing to AGOL.

This script supports force-updating specific tables via CLI parameter.
"""

import argparse
import sys
from typing import List, Optional

import internal


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Pull data from SGID Internal and push to AGOL"
    )
    
    parser.add_argument(
        "--force-tables",
        type=str,
        help="Comma-separated list of tables to force update (e.g., sgid.society.cemeteries,sgid.boundaries.municipalities)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the dolly script."""
    args = parse_arguments()
    
    # Get tables to update
    if args.force_tables:
        # Parse comma-separated table names and strip whitespace
        forced_tables = [table.strip() for table in args.force_tables.split(",")]
        # Filter out empty strings
        forced_tables = [table for table in forced_tables if table]
        
        if forced_tables:
            print(f"Force updating tables: {forced_tables}")
            # Override the internal.get_updated_tables function result
            tables_to_update = forced_tables
        else:
            # Empty force-tables argument, fall back to internal logic
            tables_to_update = internal.get_updated_tables()
            print(f"Tables to update from internal logic: {tables_to_update}")
    else:
        # Use the normal logic to determine which tables need updating
        tables_to_update = internal.get_updated_tables()
        print(f"Tables to update from internal logic: {tables_to_update}")
    
    # Process the tables
    if not tables_to_update:
        print("No tables to update.")
        return
    
    print(f"Processing {len(tables_to_update)} table(s)...")
    for table in tables_to_update:
        print(f"  - {table}")
    
    print("Processing complete.")


if __name__ == "__main__":
    main()