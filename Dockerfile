# full is required for MSSQL support in GDAL
FROM ghcr.io/osgeo/gdal:ubuntu-full-3.11.3 AS base

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

# Install zsh and oh-my-zsh for better terminal experience
RUN apt-get update && apt-get install -y \
    git \
    zsh \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Oh My Zsh for root user
RUN sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# Install zsh-autosuggestions plugin
RUN git clone https://github.com/zsh-users/zsh-autosuggestions /root/.oh-my-zsh/custom/plugins/zsh-autosuggestions

# Create proper .zshrc configuration
RUN printf '# Path to your oh-my-zsh installation.\nexport ZSH="$HOME/.oh-my-zsh"\n\n# Set name of the theme to load\nZSH_THEME="robbyrussell"\n\n# Which plugins would you like to load?\nplugins=(git zsh-autosuggestions)\n\nsource $ZSH/oh-my-zsh.sh\n\n# History configuration\nHISTSIZE=10000\nSAVEHIST=10000\nHISTFILE=/root/.zsh_history\nsetopt HIST_IGNORE_DUPS\nsetopt HIST_FIND_NO_DUPS\nsetopt SHARE_HISTORY\nsetopt APPEND_HISTORY\n\n# Enable autosuggestions\nZSH_AUTOSUGGEST_HIGHLIGHT_STYLE="fg=#666666"\n' > /root/.zshrc

# Set zsh as the default shell
RUN chsh -s $(which zsh)


FROM base AS test

ENV APP_ENVIRONMENT=dev

COPY . /app

WORKDIR /app

# Create dummy secrets file for testing
RUN cp /app/src/dolly/secrets/secrets_template.json /app/src/dolly/secrets/secrets.json

# use -e so that the secrets file will be used in the tests
RUN pip install -e .[tests] --break-system-packages


FROM base AS prod

COPY . /app

WORKDIR /app

RUN pip install . --break-system-packages

CMD ["dolly"]
