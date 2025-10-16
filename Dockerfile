# Use the Home Assistant base image's ARG for architecture
ARG BUILD_FROM
FROM $BUILD_FROM

# Add ARGs for s6-overlay
ARG S6_OVERLAY_VERSION="v3.1.6.2"
ARG BUILD_ARCH

# It downloads and extracts s6-overlay into the correct, executable layers.
ADD https://github.com/just-containers/s6-overlay/releases/download/${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /
ADD https://github.com/just-containers/s6-overlay/releases/download/${S6_OVERLAY_VERSION}/s6-overlay-${BUILD_ARCH}.tar.xz /

# Use bash as shell with better error handling
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set environment variables
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Install base packages and dependencies (your section, no changes needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential make meson ninja-build git pkg-config valac gtk-doc-tools \
    libsane1 libsane-dev sane-utils sane-airscan \
    libgirepository1.0-dev gobject-introspection \
    python3 python3-gi python3-pil python3-fastapi python3-uvicorn python3-httpx python3-pydantic \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Build and install libinsane from source (your section, no changes needed)
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

# === CHANGED SECTION ===
# Copy only your addon's custom configuration files, not the whole rootfs
# This assumes your services.d, cont-init.d, etc. are in your local 'rootfs' folder
COPY rootfs/ /

# Make your custom scripts executable.
# DO NOT chmod /init anymore. The s6-overlay install handles that.
RUN chmod +x /etc/services.d/scanner/run \
    && chmod +x /etc/services.d/scanner/finish \
    && chmod +x /etc/cont-init.d/10-config \
    && chmod +x /usr/local/bin/run.sh

# Expose the API port
EXPOSE 8099

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8099/healthz || exit 1

# Entrypoint remains the same, but now it points to the correctly installed /init
ENTRYPOINT ["/init"]