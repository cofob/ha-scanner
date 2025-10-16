ARG BUILD_FROM
FROM $BUILD_FROM

# Use bash as shell with better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set environment variables
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Install base packages and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools (needed for libinsane)
    build-essential \
    make \
    meson \
    ninja-build \
    git \
    pkg-config \
    valac \
    gtk-doc-tools \
    # Runtime libraries for libinsane and SANE
    libsane1 \
    libsane-dev \
    sane-utils \
    sane-airscan \
    # GObject Introspection
    libgirepository1.0-dev \
    gobject-introspection \
    # Python environment and all dependencies from apt
    python3 \
    python3-gi \
    python3-pil \
    python3-fastapi \
    python3-uvicorn \
    python3-httpx \
    python3-pydantic \
    # System utilities
    ca-certificates \
    curl \
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

# Set working directory for our application
WORKDIR /opt/scanner

# Copy application source files
COPY app ./app
COPY main.py ./

# Copy Home Assistant addon rootfs
COPY rootfs /

# Make scripts executable and ensure /init has correct permissions
RUN chmod +x /etc/services.d/scanner/run \
    && chmod +x /etc/services.d/scanner/finish \
    && chmod +x /etc/cont-init.d/10-config \
    && chmod +x /usr/local/bin/run.sh \
    && chmod +x /init || true

# Expose the API port
EXPOSE 8099

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8099/healthz || exit 1

# Use the s6-overlay init system
ENTRYPOINT ["/init"]