.PHONY: install test audit precision benchmark pde serve fortran-build clean

PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
WORKBENCH ?= .venv/bin/f2py-workbench

install:
	$(PYTHON) -m pip install -e ".[tests,lint]" --no-build-isolation

test:
	$(PYTEST) -v

audit:
	$(WORKBENCH) audit --cmap modern

precision:
	$(WORKBENCH) precision

benchmark:
	$(WORKBENCH) benchmark --workload dot_product --size 5000

pde:
	$(WORKBENCH) pde --steps 35 --alpha 0.01 --pulse gaussian

serve:
	$(WORKBENCH) serve --host 127.0.0.1 --port 8080

fortran-build:
	meson setup builddir --wipe || meson setup builddir
	meson compile -C builddir
	meson test -C builddir -v

clean:
	rm -rf builddir .pytest_cache *.egg-info
