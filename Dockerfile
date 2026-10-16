FROM python:3.12-slim

LABEL org.opencontainers.image.title="F2PY Scientific Computing Workbench v5.0.0"
LABEL org.opencontainers.image.description="Zero-setup Fortran 77/90/2008 + NumPy F2PY & ISO_C_BINDING scientific workbench"
LABEL org.opencontainers.image.version="5.0.0"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gfortran \
    build-essential \
    meson \
    ninja-build \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace

RUN pip install --upgrade pip meson-python ninja numpy fastapi uvicorn pytest httpx && \
    pip install --no-build-isolation -e . && \
    meson setup builddir && \
    meson compile -C builddir

EXPOSE 8765

CMD ["f2py-workbench", "serve", "--host", "0.0.0.0", "--port", "8765"]
