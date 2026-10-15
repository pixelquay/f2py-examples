# f2py Examples

![Actions Status](https://github.com/scivision/f2py-examples/workflows/ci/badge.svg)

Simple examples of using `f2py` to get high-speed Fortran integrated with Python easily.
These examples are also useful to troubleshoot problems with `f2py`.

## Build

Fortran compiler is needed:

* Mac: `brew install gcc`
* Linux: `apt install gfortran`  or  `yum install gfortran`
* [Windows](https://www.scivision.dev/install-msys2-windows)

### Install

```sh
pip install -e .
```

This will compile the Fortran code (in `.f` and `.f90` files).
It creates a file `pyprod.*` where `*` depends on operating system and Python version:

* Linux/Mac: `.so`
* Windows: `.pyd`

## Examples

### .f2py_f2cmap required

A file `.f2py_f2cmap` as in this repository must be in the top-level (same as setup.py) of the project directory tree.
If this file is missing, all "real" kinds map to float32, which is not in general what is wanted.
A missing .f2py_f2cmap will lead float64 values to be completely incorrect.

The names in the .f2py_f2cmap must exactly match the Fortran variable names used for the real kind.
If you use dp=>real64 in the Fortran code, then .f2py_f2cmap must map `dp` as well.

### Fortran Intents

```sh
python f2py_demo.py
```

output:

```
x = 3
y = 2
x * y = 6.0
Your system did this in Python using Fortran-compiled library
```

### Fortran comment syntax

Fortran 77 is officially full-line comments only. Inline comments are
not allowed with `f2py` as a result in Fortran 77 files. Demonstrate
this with:
```sh
f2py -m badcomment -c badcomment.f
```

## Troubleshooting f2py

`f2py` normally Just Works on Linux, MacOS and
[Windows Subsystem for Linux](https://www.scivision.dev/tags/windows-subsystem-for-linux).
However, Windows itself can be more challenging due to inconsistencies in Microsoft Visual Studio.

See the Windows f2py installation guide and troubleshooting
[guide](https://www.scivision.dev/f2py-fortran-python-windows/).

## Production Web Workbench, Native Fortran CLI & SDK (`demof2py` v3.0.0)

Launch the interactive Fortran–Python Web Workbench and FastAPI service:

```sh
f2py-workbench serve --host 127.0.0.1 --port 8080
```

Or run CLI diagnostics, 1D Heat Diffusion PDE simulations, 4th-order Runge-Kutta (`RK4`) oscillator integration, 2D Poisson PDE Jacobi relaxation, column-major matrix & Simpson quadrature evaluations, catastrophic cancellation root stability analysis, and `gfortran` syntax verification directly:

```sh
f2py-workbench demo -x 3 -y 2
f2py-workbench precision
f2py-workbench benchmark --workload dot_product --size 5000
f2py-workbench pde --steps 35 --alpha 0.01 --pulse gaussian
f2py-workbench ode --steps 120 --zeta 0.15
f2py-workbench poisson -n 15 --iterations 80 --source dipole
f2py-workbench numerics --preset spd_stiffness --order F --integrand poly_quartic --points 31
f2py-workbench quadratic -a 1.0 -b 1e8 -c 1.0
f2py-workbench audit --cmap modern --compile-check
```

### Standalone Native Fortran 2008 CLI (`fortran_workbench`)

Compile and run the standalone native Fortran 2008 numerical workbench binary via Meson:

```sh
meson setup builddir
meson compile -C builddir
./builddir/fortran_workbench --all
```


