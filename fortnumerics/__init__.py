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

    @staticmethod
    def rk4harmonicstep(
        steps: int,
        dt: float,
        omega0: float,
        zeta: float,
        x0: float,
        v0: float,
    ) -> Tuple[NDArray[np.float64], NDArray[np.float64], float]:
        """
        Subroutine Rk4HarmonicStep(steps, dt, omega0, zeta, x0, v0, x_traj, v_traj, final_energy)
        4th-order Runge-Kutta (RK4) integrator for the damped harmonic oscillator.
        Returns (x_traj, v_traj, final_energy).
        """
        n_steps = max(1, int(steps))
        dt_f = float(dt)
        w0_f = float(omega0)
        z_f = float(zeta)
        w2 = w0_f * w0_f
        c_damp = 2.0 * z_f * w0_f

        x_traj = np.zeros(n_steps + 1, dtype=np.float64)
        v_traj = np.zeros(n_steps + 1, dtype=np.float64)
        x = float(x0)
        v = float(v0)
        x_traj[0] = x
        v_traj[0] = v

        for s in range(n_steps):
            kx1 = v
            kv1 = -c_damp * v - w2 * x

            kx2 = v + 0.5 * dt_f * kv1
            kv2 = -c_damp * kx2 - w2 * (x + 0.5 * dt_f * kx1)

            kx3 = v + 0.5 * dt_f * kv2
            kv3 = -c_damp * kx3 - w2 * (x + 0.5 * dt_f * kx2)

            kx4 = v + dt_f * kv3
            kv4 = -c_damp * kx4 - w2 * (x + dt_f * kx3)

            x = x + (dt_f / 6.0) * (kx1 + 2.0 * kx2 + 2.0 * kx3 + kx4)
            v = v + (dt_f / 6.0) * (kv1 + 2.0 * kv2 + 2.0 * kv3 + kv4)
            x_traj[s + 1] = x
            v_traj[s + 1] = v

        final_energy = float(0.5 * (v * v + w2 * x * x))
        return x_traj, v_traj, final_energy

    @staticmethod
    def jacobipoisson2d(
        iterations: int,
        rhs: Union[Sequence[Sequence[float]], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float, float]:
        """
        Subroutine JacobiPoisson2D(n, iterations, rhs, u_out, max_residual, l2_norm)
        2D Poisson PDE solver (-Laplacian(u) = rhs) on an n x n unit square grid.
        Returns (u_out, max_residual, l2_norm).
        """
        rhs_arr = np.asarray(rhs, dtype=np.float64, order="F")
        if rhs_arr.ndim != 2 or rhs_arr.shape[0] != rhs_arr.shape[1]:
            raise ValueError("JacobiPoisson2D requires a square 2D rhs array.")
        n = int(rhs_arr.shape[0])
        if n < 3:
            raise ValueError("JacobiPoisson2D requires grid size n >= 3.")
        h2 = (1.0 / float(n - 1)) ** 2
        u_curr = np.zeros((n, n), dtype=np.float64, order="F")
        u_next = np.zeros((n, n), dtype=np.float64, order="F")

        for _ in range(max(1, int(iterations))):
            u_next[1:-1, 1:-1] = 0.25 * (
                u_curr[:-2, 1:-1]
                + u_curr[2:, 1:-1]
                + u_curr[1:-1, :-2]
                + u_curr[1:-1, 2:]
                + h2 * rhs_arr[1:-1, 1:-1]
            )
            u_curr[:, :] = u_next

        lap_u = (
            4.0 * u_curr[1:-1, 1:-1]
            - u_curr[:-2, 1:-1]
            - u_curr[2:, 1:-1]
            - u_curr[1:-1, :-2]
            - u_curr[1:-1, 2:]
        ) / h2
        max_residual = float(np.max(np.abs(lap_u - rhs_arr[1:-1, 1:-1])))
        l2_norm = float(np.sqrt(np.sum(u_curr * u_curr) * h2))
        return u_curr, max_residual, l2_norm


fortnumerics = _FortNumericsModule()

__all__ = ["fortnumerics"]

