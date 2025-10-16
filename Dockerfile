ARG BUILD_FROM
FROM $BUILD_FROM

# Use bash as shell with better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set environment variables
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Install base packages and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools
    build-essential \
    make \
    meson \
    ninja-build \
    git \
    pkg-config \
    # Runtime libraries for libinsane and SANE
    libsane1 \
    libsane-dev \
    sane-utils \
    sane-airscan \
    # GObject Introspection
    libgirepository1.0-dev \
    gobject-introspection \
    # Python environment
    python3 \
    python3-gi \
    python3-dev \
    python3-venv \
    # Image libraries (for PIL)
    libjpeg62-turbo \
    libtiff6 \
    libpng16-16 \
    libwebp7 \
    zlib1g \
    libopenjp2-7 \
    # System utilities
    ca-certificates \
    curl \
    # Vala and GTK-doc for libinsane-gobject
    valac \
    gtk-doc-tools \
    && rm -rf /var/lib/apt/lists/*

# Build and install libinsane from source
RUN git clone --depth=1 https://gitlab.gnome.org/World/OpenPaperwork/libinsane.git /tmp/libinsane && \
    cd /tmp/libinsane && \
    make PREFIX=/usr && \
    make test PREFIX=/usr || true && \
    make install PREFIX=/usr && \
    ldconfig && \
    cd / && \
    rm -rf /tmp/libinsane

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv ~/.local/bin/uv /usr/local/bin/uv

# Set working directory for our application
WORKDIR /opt/scanner

# Copy project files first for dependency resolution
COPY pyproject.toml uv.lock ./

# Install dependencies directly with uv pip, excluding pygobject (use system version)
# Override external management for container environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --python=python3 --break-system-packages \
        "fastapi>=0.104.0" \
        "uvicorn[standard]>=0.24.0" \
        "httpx>=0.25.0" \
        "pydantic>=2.5.0" \
        "python-json-logger>=2.0.0" \
        "pillow>=12.0.0"

# Copy project source files
COPY app ./app
COPY main.py ./

# Install the project itself into system Python
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --python=python3 --break-system-packages -e .

# Copy Home Assistant addon rootfs
COPY rootfs /

# Make scripts executable
RUN chmod +x /etc/services.d/scanner/run \
    && chmod +x /etc/services.d/scanner/finish \
    && chmod +x /etc/cont-init.d/10-config \
    && chmod +x /usr/local/bin/run.sh

# Clean up build dependencies to reduce image size
RUN apt-get purge -y \
    build-essential \
    make \
    meson \
    ninja-build \
    git \
    pkg-config \
    python3-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Expose the API port
EXPOSE 8099

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8099/healthz || exit 1

# Use the s6-overlay init system
ENTRYPOINT ["/init"]