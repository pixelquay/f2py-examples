"""
fortnumerics: Python/NumPy f2py interface to numerics.f90.

Provides exact column-major Fortran 2008 numerical routines:
- matmuldp(a, b) -> C (real64 matrix product)
- heat1dstep(steps, alpha, dx, dt, u_init) -> (u_final, cfl_number, l2_energy)
- simpsonintegratedp(dx, y) -> integral
- quadraticrootscompare(a, b, c) -> (r1_naive, r2_naive, r1_stable, r2_stable, cancel_err)
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple, Union
import numpy as np
from numpy.typing import NDArray


class _FortNumericsModule:
    """Fortran module `fortnumerics` wrapped with exact f2py calling conventions."""

    @staticmethod
    def matmuldp(
        a: Union[Sequence[Sequence[float]], NDArray[np.floating]],
        b: Union[Sequence[Sequence[float]], NDArray[np.floating]],
    ) -> NDArray[np.float64]:
        """
        Subroutine MatMulDp(m, k, n, a, b, c)
        Column-major (Fortran order='F') double-precision matrix product C = A @ B.
        """
        am = np.asarray(a, dtype=np.float64, order="F")
        bm = np.asarray(b, dtype=np.float64, order="F")
        if am.ndim != 2 or bm.ndim != 2:
            raise ValueError("MatMulDp requires 2D input matrices.")
        if am.shape[1] != bm.shape[0]:
            raise ValueError(
                f"Matrix inner dimensions must match: {am.shape} vs {bm.shape}"
            )
        return np.asarray(am @ bm, dtype=np.float64, order="F")

    @staticmethod
    def heat1dstep(
        steps: int,
        alpha: float,
        dx: float,
        dt: float,
        u_init: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float, float]:
        """
        Subroutine Heat1DStep(n, steps, alpha, dx, dt, u_init, u_final, cfl_number, l2_energy)
        1D Heat Diffusion PDE explicit finite-difference stencil solver.
        Returns (u_final, cfl_number, l2_energy).
        """
        u0 = np.asarray(u_init, dtype=np.float64).ravel()
        n = int(u0.shape[0])
        if n < 3:
            raise ValueError("Heat1DStep requires at least 3 spatial grid points.")
        cfl_number = float(alpha * dt / (dx * dx))
        u_curr = u0.copy()
        u_next = u0.copy()

        for _ in range(int(steps)):
            u_next[0] = u_curr[0]
            u_next[1:-1] = u_curr[1:-1] + cfl_number * (
                u_curr[:-2] - 2.0 * u_curr[1:-1] + u_curr[2:]
            )
            u_next[-1] = u_curr[-1]
            u_curr[:] = u_next

        l2_energy = float(np.sqrt(np.sum(u_curr * u_curr) * dx))
        return u_curr, cfl_number, l2_energy

    @staticmethod
    def simpsonintegratedp(
        dx: float,
        y: Union[Sequence[float], NDArray[np.floating]],
    ) -> float:
        """
        Subroutine SimpsonIntegrateDp(n, dx, y, integral)
        Composite Simpson's 1/3 quadrature rule (with trapezoidal tail if n is even).
        """
        ya = np.asarray(y, dtype=np.float64).ravel()
        n = int(ya.shape[0])
        if n < 2:
            return 0.0
        if n == 2:
            return float(0.5 * dx * (ya[0] + ya[1]))

        m_odd = n
        acc = 0.0
        if n % 2 == 0:
            acc = float(0.5 * dx * (ya[-2] + ya[-1]))
            m_odd = n - 1

        sub = ya[:m_odd]
        total = (
            sub[0]
            + sub[-1]
            + 4.0 * float(np.sum(sub[1:-1:2]))
            + 2.0 * float(np.sum(sub[2:-2:2]))
        )
        return float((dx / 3.0) * total + acc)

    @staticmethod
    def quadraticrootscompare(
        a: float,
        b: float,
        c: float,
    ) -> Tuple[float, float, float, float, float]:
        """
        Subroutine QuadraticRootsCompare(a, b, c, r1_naive, r2_naive, r1_stable, r2_stable, cancel_err)
        Compares textbook quadratic roots vs Citardauq stable roots.
        """
        af = float(np.float64(a))
        bf = float(np.float64(b))
        cf = float(np.float64(c))
        disc = max(0.0, bf * bf - 4.0 * af * cf)
        sqrt_disc = math.sqrt(disc)

        r1_naive = (-bf - sqrt_disc) / (2.0 * af)
        r2_naive = (-bf + sqrt_disc) / (2.0 * af)

        if bf >= 0.0:
            q = -0.5 * (bf + sqrt_disc)
            r1_stable = q / af
            r2_stable = cf / q if q != 0.0 else 0.0
        else:
            q = -0.5 * (bf - sqrt_disc)
            r1_stable = cf / q if q != 0.0 else 0.0
            r2_stable = q / af

        cancel_err = max(abs(r1_naive - r1_stable), abs(r2_naive - r2_stable))
        return r1_naive, r2_naive, r1_stable, r2_stable, cancel_err


fortnumerics = _FortNumericsModule()

__all__ = ["fortnumerics"]
