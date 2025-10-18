ARG BUILD_FROM
FROM $BUILD_FROM

ENV PYTHONUNBUFFERED=1

# Install base packages and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential make meson ninja-build git pkg-config valac gtk-doc-tools \
    libsane1 libsane-dev sane-utils sane-airscan \
    libgirepository1.0-dev gobject-introspection \
    python3 python3-gi python3-pil python3-fastapi python3-uvicorn python3-httpx python3-pydantic \
    ca-certificates curl \
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

WORKDIR /opt/scanner

COPY rootfs/ /

COPY app ./app
COPY main.py ./

EXPOSE 8099