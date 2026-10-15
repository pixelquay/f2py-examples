#!/usr/bin/env python3
"""
Modernized setup.py compatible with NumPy 2.x and Python 3.12+.
Uses setuptools and optionally compiles Fortran extensions via f2py when a Fortran
compiler (gfortran) is present, while installing the Python/NumPy bridge packages.
"""
import site
from setuptools import setup

site.ENABLE_USER_SITE = True

setup()

