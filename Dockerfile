# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gfortran \
    gcc \
    libc6-dev \
    meson \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace

# Compile native Fortran 2008 libraries and standalone CLI binary via Meson
RUN meson setup builddir && meson compile -C builddir && meson test -C builddir

# Install Python package and FastAPI Workbench dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[tests]"

FROM python:3.12-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgfortran5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/f2py-workbench /usr/local/bin/f2py-workbench
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /workspace /app
COPY --from=builder /workspace/builddir/fortran_workbench /usr/local/bin/fortran_workbench

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health')" || exit 1

CMD ["f2py-workbench", "serve", "--host", "0.0.0.0", "--port", "8080"]
