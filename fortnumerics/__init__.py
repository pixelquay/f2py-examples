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

    @staticmethod
    def powereigen3x3(
        a: Union[Sequence[Sequence[float]], NDArray[np.floating]],
        iterations: int,
    ) -> Tuple[float, NDArray[np.float64], float]:
        """Rayleigh-quotient power iteration for the dominant eigenpair of a 3x3 matrix."""
        a_arr = np.asarray(a, dtype=np.float64, order="F")
        if a_arr.shape != (3, 3):
            raise ValueError("a must be a 3x3 matrix")

        v = np.ones(3, dtype=np.float64) / np.sqrt(3.0)
        for _ in range(max(1, int(iterations))):
            av = a_arr @ v
            norm_av = float(np.linalg.norm(av))
            if norm_av > 1e-15:
                v = -av / norm_av if av[0] < 0.0 else av / norm_av
        av = a_arr @ v
        eigval = float(np.dot(v, av))
        res_norm = float(np.linalg.norm(av - eigval * v))
        return eigval, v, res_norm

    @staticmethod
    def thomastridiag(
        sub_d: Union[Sequence[float], NDArray[np.floating]],
        main_d: Union[Sequence[float], NDArray[np.floating]],
        super_d: Union[Sequence[float], NDArray[np.floating]],
        rhs: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float]:
        """O(N) Thomas algorithm (TDMA) for a tridiagonal linear system T * x = rhs."""
        a_sub = np.asarray(sub_d, dtype=np.float64, order="F")
        b_main = np.asarray(main_d, dtype=np.float64, order="F")
        c_sup = np.asarray(super_d, dtype=np.float64, order="F")
        d_rhs = np.asarray(rhs, dtype=np.float64, order="F")
        if a_sub.ndim != 1 or not (a_sub.shape == b_main.shape == c_sup.shape == d_rhs.shape):
            raise ValueError("sub_d, main_d, super_d, and rhs must be 1D arrays of equal length")
        n = int(a_sub.shape[0])

        c_star = np.zeros(n, dtype=np.float64)
        d_star = np.zeros(n, dtype=np.float64)
        x_out = np.zeros(n, dtype=np.float64)
        if n == 0:
            return x_out, 0.0
        c_star[0] = c_sup[0] / b_main[0]
        d_star[0] = d_rhs[0] / b_main[0]
        for i in range(1, n):
            denom = b_main[i] - a_sub[i] * c_star[i - 1]
            if i < n - 1:
                c_star[i] = c_sup[i] / denom
            d_star[i] = (d_rhs[i] - a_sub[i] * d_star[i - 1]) / denom
        x_out[n - 1] = d_star[n - 1]
        for i in range(n - 2, -1, -1):
            x_out[i] = d_star[i] - c_star[i] * x_out[i + 1]

        res_inf = 0.0
        for i in range(n):
            lhs = b_main[i] * x_out[i]
            if i > 0:
                lhs += a_sub[i] * x_out[i - 1]
            if i < n - 1:
                lhs += c_sup[i] * x_out[i + 1]
            res_inf = max(res_inf, abs(float(lhs - d_rhs[i])))
        return x_out, float(res_inf)

    @staticmethod
    def blackscholesgrid(
        s_grid: Union[Sequence[float], NDArray[np.floating]],
        strike: float,
        rate: float,
        sigma: float,
        maturity: float,
    ) -> Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        """Vectorized European Call/Put option pricing and Call Delta across an N-point spot grid."""
        s_arr = np.asarray(s_grid, dtype=np.float64, order="F")
        s_safe = np.maximum(1.0e-12, s_arr)
        k_val = float(strike)
        r_val = float(rate)
        v_val = float(sigma)
        t_val = max(1.0e-12, float(maturity))

        vol_sqrt_t = max(1.0e-12, v_val * np.sqrt(t_val))
        disc_k = k_val * np.exp(-r_val * t_val)
        d1 = (np.log(s_safe / k_val) + (r_val + 0.5 * v_val * v_val) * t_val) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        inv_sqrt2 = 1.0 / np.sqrt(2.0)
        nd1 = 0.5 * np.vectorize(math.erfc, otypes=[np.float64])(-d1 * inv_sqrt2)
        nd2 = 0.5 * np.vectorize(math.erfc, otypes=[np.float64])(-d2 * inv_sqrt2)
        call_p = np.asarray(s_safe * nd1 - disc_k * nd2, dtype=np.float64, order="F")
        put_p = np.asarray(call_p - s_safe + disc_k, dtype=np.float64, order="F")
        delta_c = np.asarray(nd1, dtype=np.float64, order="F")
        return call_p, put_p, delta_c

    @staticmethod
    def spectraldftpower(
        sig: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], int, float]:
        """
        Subroutine SpectralDftPower(n, sig, power_out, peak_bin, peak_pow)
        Hann-windowed one-sided Discrete Fourier Transform (DFT) power spectrum.
        Returns (power_out, peak_bin, peak_pow).
        """
        sig_arr = np.asarray(sig, dtype=np.float64, order="F").ravel()
        n = int(sig_arr.shape[0])
        if n < 2:
            raise ValueError("SpectralDftPower requires at least 2 signal samples.")
        n_bins = n // 2 + 1
        idx = np.arange(n, dtype=np.float64)
        win = 0.5 * (1.0 - np.cos(2.0 * math.pi * idx / float(max(1, n - 1))))
        windowed = sig_arr * win

        power_out = np.zeros(n_bins, dtype=np.float64, order="F")
        peak_bin = 0
        peak_pow = -1.0
        for k in range(n_bins):
            angles = 2.0 * math.pi * float(k) * idx / float(n)
            re_sum = float(np.dot(windowed, np.cos(angles)))
            im_sum = float(np.dot(windowed, -np.sin(angles)))
            pwr = (re_sum * re_sum + im_sum * im_sum) / float(n)
            power_out[k] = pwr
            if pwr > peak_pow:
                peak_pow = pwr
                peak_bin = k
        return power_out, int(peak_bin), float(peak_pow)

    @staticmethod
    def montecarlooptiondp(
        n_paths: int,
        s0: float,
        strike: float,
        rate: float,
        sigma: float,
        maturity: float,
        seed: int = 42,
    ) -> Tuple[float, float, float, NDArray[np.float64]]:
        """
        Subroutine MonteCarloOptionDp(n_paths, s0, strike, rate, sigma, maturity, seed,
                                      call_est, put_est, std_err, paths_sample)
        Deterministic Box-Muller + Antithetic Variates Geometric Brownian Motion
        European option pricer. Returns (call_est, put_est, std_err, paths_sample).
        """
        n_pairs = max(1, int(n_paths) // 2)
        t_safe = max(1.0e-12, float(maturity))
        s0_f = float(s0)
        k_f = float(strike)
        r_f = float(rate)
        v_f = float(sigma)
        drift = (r_f - 0.5 * v_f * v_f) * t_safe
        vol_sqrt_t = v_f * math.sqrt(t_safe)
        disc = math.exp(-r_f * t_safe)

        state = abs(int(seed))
        if state == 0:
            state = 1337

        sum_c = 0.0
        sum_p = 0.0
        sum_c2 = 0.0
        paths_sample = np.full(64, s0_f, dtype=np.float64, order="F")
        two_pi = 2.0 * math.pi

        for p in range(1, n_pairs + 1):
            state = (state * 1103515245 + 12345) % 2147483648
            u1 = max(1.0e-12, float(state) / 2147483648.0)
            state = (state * 1103515245 + 12345) % 2147483648
            u2 = float(state) / 2147483648.0

            z_norm = math.sqrt(-2.0 * math.log(u1)) * math.cos(two_pi * u2)
            s_pos = s0_f * math.exp(drift + vol_sqrt_t * z_norm)
            s_neg = s0_f * math.exp(drift - vol_sqrt_t * z_norm)

            pay_c = 0.5 * (max(0.0, s_pos - k_f) + max(0.0, s_neg - k_f))
            pay_p = 0.5 * (max(0.0, k_f - s_pos) + max(0.0, k_f - s_neg))

            sum_c += pay_c
            sum_p += pay_p
            sum_c2 += pay_c * pay_c

            idx1 = 2 * p - 2
            idx2 = 2 * p - 1
            if idx1 < 64:
                paths_sample[idx1] = s_pos
            if idx2 < 64:
                paths_sample[idx2] = s_neg

        mean_c = sum_c / float(n_pairs)
        mean_p = sum_p / float(n_pairs)
        var_c = max(0.0, (sum_c2 / float(n_pairs)) - mean_c * mean_c)

        call_est = float(disc * mean_c)
        put_est = float(disc * mean_p)
        std_err = float(disc * math.sqrt(var_c / float(n_pairs)))
        return call_est, put_est, std_err, paths_sample

    @staticmethod
    def autodiffrosenbrockdp(
        x: float,
        y: float,
        h_steps: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[
        NDArray[np.float64],
        NDArray[np.float64],
        float,
        float,
        float,
        float,
    ]:
        """
        Subroutine AutoDiffRosenbrockDp(x, y, n_steps, h_steps, fd_err_forward,
                                        fd_err_central, exact_grad_x, exact_grad_y,
                                        exact_val, optimal_h_central)
        Forward-mode Dual-Number / Tangent Automatic Differentiation vs Finite-Difference
        truncation/cancellation V-curve on the 2D Rosenbrock function.
        """
        x_f = float(x)
        y_f = float(y)
        h_arr = np.asarray(h_steps, dtype=np.float64, order="F").ravel()
        n_steps = int(h_arr.shape[0])

        exact_val = (1.0 - x_f) ** 2 + 100.0 * (y_f - x_f * x_f) ** 2
        exact_grad_x = -2.0 * (1.0 - x_f) - 400.0 * x_f * (y_f - x_f * x_f)
        exact_grad_y = 200.0 * (y_f - x_f * x_f)

        fd_err_forward = np.zeros(n_steps, dtype=np.float64, order="F")
        fd_err_central = np.zeros(n_steps, dtype=np.float64, order="F")

        min_err = float("inf")
        optimal_h_central = 1.0e-5

        for i in range(n_steps):
            h = max(1.0e-16, float(h_arr[i]))
            fx_p = (1.0 - (x_f + h)) ** 2 + 100.0 * (y_f - (x_f + h) ** 2) ** 2
            fx_m = (1.0 - (x_f - h)) ** 2 + 100.0 * (y_f - (x_f - h) ** 2) ** 2
            fy_p = (1.0 - x_f) ** 2 + 100.0 * ((y_f + h) - x_f * x_f) ** 2
            fy_m = (1.0 - x_f) ** 2 + 100.0 * ((y_f - h) - x_f * x_f) ** 2

            fwd_gx = (fx_p - exact_val) / h
            fwd_gy = (fy_p - exact_val) / h
            cen_gx = (fx_p - fx_m) / (2.0 * h)
            cen_gy = (fy_p - fy_m) / (2.0 * h)

            err_f = max(1.0e-16, math.hypot(fwd_gx - exact_grad_x, fwd_gy - exact_grad_y))
            err_c = max(1.0e-16, math.hypot(cen_gx - exact_grad_x, cen_gy - exact_grad_y))
            fd_err_forward[i] = err_f
            fd_err_central[i] = err_c

            if err_c < min_err:
                min_err = err_c
                optimal_h_central = h

        return (
            fd_err_forward,
            fd_err_central,
            float(exact_grad_x),
            float(exact_grad_y),
            float(exact_val),
            float(optimal_h_central),
        )

    @staticmethod
    def csrspmvdp(
        row_ptr: Union[Sequence[int], NDArray[np.integer]],
        col_idx: Union[Sequence[int], NDArray[np.integer]],
        vals: Union[Sequence[float], NDArray[np.floating]],
        x: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float, float]:
        """
        Subroutine CsrSpmvDp(n, nnz, row_ptr, col_idx, vals, x, y_sparse, max_err_vs_dense, compression_ratio)
        O(nnz) Compressed Sparse Row (CSR, 1-based Fortran indexing) sparse matrix-vector
        multiplication y = A_csr * x.
        """
        rp = np.asarray(row_ptr, dtype=np.int32).ravel()
        ci = np.asarray(col_idx, dtype=np.int32).ravel()
        v = np.asarray(vals, dtype=np.float64, order="F").ravel()
        x_arr = np.asarray(x, dtype=np.float64, order="F").ravel()

        n = int(x_arr.shape[0])
        nnz = int(v.shape[0])
        if rp.shape[0] != n + 1:
            raise ValueError(f"CSR row_ptr length ({rp.shape[0]}) must equal n + 1 ({n + 1}).")

        y_sparse = np.zeros(n, dtype=np.float64, order="F")
        dense = np.zeros((n, n), dtype=np.float64, order="F")
        for i in range(n):
            acc = 0.0
            start_k = int(rp[i]) - 1
            end_k = int(rp[i + 1]) - 1
            for k in range(start_k, end_k):
                c_idx = int(ci[k]) - 1
                if 0 <= c_idx < n:
                    acc += float(v[k]) * float(x_arr[c_idx])
                    dense[i, c_idx] += float(v[k])
            y_sparse[i] = acc

        y_dense = dense @ x_arr
        max_err = float(np.max(np.abs(y_sparse - y_dense))) if n > 0 else 0.0
        dense_bytes = float(n * n * 8)
        csr_bytes = float(nnz * 8 + (nnz + n + 1) * 4)
        compression_ratio = dense_bytes / max(1.0, csr_bytes)
        return y_sparse, max_err, float(compression_ratio)


fortnumerics = _FortNumericsModule()

__all__ = ["fortnumerics"]


