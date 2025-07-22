# full is required for MSSQL support in GDAL
FROM ghcr.io/osgeo/gdal:ubuntu-full-3.11.0 AS base

# Set environment variables to prevent interactive prompts during apt-get install
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

# Install core utilities and Python 3.12
# Ubuntu 24.04 comes with Python 3.12 by default, so we just need pip.
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip

# Download the Microsoft GPG key, de-armor it, and place it in trusted.gpg.d
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft.gpg \
    # Add the Microsoft SQL Server Ubuntu 24.04 repository to sources.list.d
    # Use 'noble' for Ubuntu 24.04's codename
    && echo "deb [arch=amd64,arm64 signed-by=/etc/apt/trusted.gpg.d/microsoft.gpg] https://packages.microsoft.com/ubuntu/24.04/prod noble main" > /etc/apt/sources.list.d/mssql-release.list

# Now, update apt cache *after* the Microsoft repository is fully configured
RUN apt-get update \
    # Install the ODBC Driver 18 for SQL Server.
    # IMPORTANT: Use msodbcsql18
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    # Clean up APT cache and lists to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

FROM base AS dev_container

ENV APP_ENVIRONMENT=dev
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*


FROM base AS prod

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED=True

COPY . /app

WORKDIR /app

RUN pip install . --break-system-packages
