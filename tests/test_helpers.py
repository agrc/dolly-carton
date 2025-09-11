"""Test helper functions for feature counting functionality."""


def count_features_in_internal_table(table: str, connection=None) -> int:
    """
    Count features in an internal database table.

    This function is a placeholder that will be implemented with database connection logic.
    It's placed in tests for mocking in tests.

    Args:
        table: Table name in format "sgid.schema.table"
        connection: Database connection (optional, for dependency injection in tests)

    Returns:
        Number of features in the table

    Note:
        This function will be called from internal.py where the actual
        database connection logic will be implemented.
    """
    # This is a placeholder - actual implementation will be in internal.py
    # but the interface is defined here for testing purposes
    raise NotImplementedError(
        "This function should be called with proper database connection from internal.py"
    )


def count_features_in_fgdb_layer(fgdb_path, layer_name: str) -> int:
    """
    Count features in a File Geodatabase layer.

    This function is a placeholder that will be implemented with GDAL logic.
    It's placed in tests for mocking in tests.

    Args:
        fgdb_path: Path to the File Geodatabase
        layer_name: Name of the layer within the FGDB

    Returns:
        Number of features in the layer

    Note:
        This function will be called from internal.py where the actual
        GDAL connection logic will be implemented.
    """
    # This is a placeholder - actual implementation will use GDAL
    # but the interface is defined here for testing purposes
    raise NotImplementedError(
        "This function should be called with proper GDAL logic from internal.py"
    )


def count_features_in_agol_service(service_item) -> int:
    """
    Count features in an ArcGIS Online service.

    This function is a placeholder that will be implemented with ArcGIS API logic.
    It's placed in tests for mocking in tests.

    Args:
        service_item: ArcGIS service item (Table or FeatureLayer)

    Returns:
        Number of features in the service

    Note:
        This function will be called from agol.py where the actual
        ArcGIS API logic will be implemented.
    """
    # This is a placeholder - actual implementation will use ArcGIS API
    # but the interface is defined here for testing purposes
    raise NotImplementedError(
        "This function should be called with proper ArcGIS API logic from agol.py"
    )
