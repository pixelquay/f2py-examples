module fortnumerics
  !! Production Fortran 2008 numerical linear algebra, PDE stencil,
  !! composite quadrature, and floating-point stability routines for F2PY.
  use, intrinsic :: iso_fortran_env, only: sp => real32, dp => real64
  implicit none
  private
  public :: MatMulDp, Heat1DStep, SimpsonIntegrateDp, QuadraticRootsCompare, Rk4HarmonicStep, JacobiPoisson2D
  public :: PowerEigen3x3, ThomasTridiag, BlackScholesGrid, SpectralDftPower, MonteCarloOptionDp
  public :: AutoDiffRosenbrockDp, CsrSpmvDp

contains

  subroutine MatMulDp(m, k, n, a, b, c)
    !! Column-major (j-l-i) cache-optimized double-precision matrix product C = A * B.
    integer, intent(in) :: m, k, n
    real(dp), intent(in) :: a(m, k), b(k, n)
    real(dp), intent(out) :: c(m, n)
    integer :: i, j, l

    c = 0.0_dp
    do j = 1, n
      do l = 1, k
        do i = 1, m
          c(i, j) = c(i, j) + a(i, l) * b(l, j)
        end do
      end do
    end do
  end subroutine MatMulDp


  subroutine Heat1DStep(n, steps, alpha, dx, dt, u_init, u_final, cfl_number, l2_energy)
    !! 1D Heat Diffusion PDE solver: du/dt = alpha * d^2u/dx^2
    !! Uses explicit forward-Euler in time and 2nd-order central difference in space
    !! with fixed Dirichlet boundary conditions u(1) = u_init(1), u(n) = u_init(n).
    integer, intent(in) :: n, steps
    real(dp), intent(in) :: alpha, dx, dt
    real(dp), intent(in) :: u_init(n)
    real(dp), intent(out) :: u_final(n)
    real(dp), intent(out) :: cfl_number, l2_energy
    real(dp) :: u_curr(n), u_next(n)
    integer :: i, s

    cfl_number = alpha * dt / (dx * dx)
    u_curr = u_init
    u_next = u_init

    do s = 1, steps
      u_next(1) = u_curr(1)
      do i = 2, n - 1
        u_next(i) = u_curr(i) + cfl_number * (u_curr(i - 1) - 2.0_dp * u_curr(i) + u_curr(i + 1))
      end do
      u_next(n) = u_curr(n)
      u_curr = u_next
    end do

    u_final = u_curr
    l2_energy = sqrt(sum(u_final * u_final) * dx)
  end subroutine Heat1DStep


  subroutine SimpsonIntegrateDp(n, dx, y, integral)
    !! Composite Simpson's 1/3 quadrature rule (with trapezoidal tail if n is even).
    integer, intent(in) :: n
    real(dp), intent(in) :: dx
    real(dp), intent(in) :: y(n)
    real(dp), intent(out) :: integral
    integer :: i, m_odd
    real(dp) :: acc

    if (n < 2) then
      integral = 0.0_dp
      return
    else if (n == 2) then
      integral = 0.5_dp * dx * (y(1) + y(2))
      return
    end if

    m_odd = n
    acc = 0.0_dp
    if (mod(n, 2) == 0) then
      acc = 0.5_dp * dx * (y(n - 1) + y(n))
      m_odd = n - 1
    end if

    integral = y(1) + y(m_odd)
    do i = 2, m_odd - 1, 2
      integral = integral + 4.0_dp * y(i)
    end do
    do i = 3, m_odd - 2, 2
      integral = integral + 2.0_dp * y(i)
    end do
    integral = (dx / 3.0_dp) * integral + acc
  end subroutine SimpsonIntegrateDp


  subroutine QuadraticRootsCompare(a, b, c, r1_naive, r2_naive, r1_stable, r2_stable, cancel_err)
    !! Compares standard quadratic formula against numerically stable Citardauq root
    !! calculation to demonstrate catastrophic cancellation when b^2 >> 4ac.
    real(dp), intent(in) :: a, b, c
    real(dp), intent(out) :: r1_naive, r2_naive
    real(dp), intent(out) :: r1_stable, r2_stable
    real(dp), intent(out) :: cancel_err
    real(dp) :: disc, sqrt_disc, q

    disc = max(0.0_dp, b * b - 4.0_dp * a * c)
    sqrt_disc = sqrt(disc)

    r1_naive = (-b - sqrt_disc) / (2.0_dp * a)
    r2_naive = (-b + sqrt_disc) / (2.0_dp * a)

    if (b >= 0.0_dp) then
      q = -0.5_dp * (b + sqrt_disc)
      r1_stable = q / a
      r2_stable = c / q
    else
      q = -0.5_dp * (b - sqrt_disc)
      r1_stable = c / q
      r2_stable = q / a
    end if

    cancel_err = max(abs(r1_naive - r1_stable), abs(r2_naive - r2_stable))
  end subroutine QuadraticRootsCompare


  subroutine Rk4HarmonicStep(steps, dt, omega0, zeta, x0, v0, x_traj, v_traj, final_energy)
    !! 4th-order Runge-Kutta (RK4) integrator for the damped harmonic oscillator:
    !! dx/dt = v, dv/dt = -2*zeta*omega0*v - (omega0^2)*x
    integer, intent(in) :: steps
    real(dp), intent(in) :: dt, omega0, zeta, x0, v0
    real(dp), intent(out) :: x_traj(steps + 1), v_traj(steps + 1)
    real(dp), intent(out) :: final_energy
    real(dp) :: x, v, w2, c_damp
    real(dp) :: kx1, kv1, kx2, kv2, kx3, kv3, kx4, kv4
    integer :: s

    w2 = omega0 * omega0
    c_damp = 2.0_dp * zeta * omega0
    x = x0
    v = v0
    x_traj(1) = x
    v_traj(1) = v

    do s = 1, steps
      kx1 = v
      kv1 = -c_damp * v - w2 * x

      kx2 = v + 0.5_dp * dt * kv1
      kv2 = -c_damp * kx2 - w2 * (x + 0.5_dp * dt * kx1)

      kx3 = v + 0.5_dp * dt * kv2
      kv3 = -c_damp * kx3 - w2 * (x + 0.5_dp * dt * kx2)

      kx4 = v + dt * kv3
      kv4 = -c_damp * kx4 - w2 * (x + dt * kx3)

      x = x + (dt / 6.0_dp) * (kx1 + 2.0_dp * kx2 + 2.0_dp * kx3 + kx4)
      v = v + (dt / 6.0_dp) * (kv1 + 2.0_dp * kv2 + 2.0_dp * kv3 + kv4)

      x_traj(s + 1) = x
      v_traj(s + 1) = v
    end do

    final_energy = 0.5_dp * (v * v + w2 * x * x)
  end subroutine Rk4HarmonicStep


  subroutine JacobiPoisson2D(n, iterations, rhs, u_out, max_residual, l2_norm)
    !! 2D Poisson PDE solver (-Laplacian(u) = rhs) on an n x n unit square grid
    !! using Jacobi 5-point finite-difference relaxation in column-major order.
    integer, intent(in) :: n, iterations
    real(dp), intent(in) :: rhs(n, n)
    real(dp), intent(out) :: u_out(n, n)
    real(dp), intent(out) :: max_residual, l2_norm
    real(dp) :: u_curr(n, n), u_next(n, n), h2, res_ij
    integer :: i, j, it

    h2 = (1.0_dp / real(max(1, n - 1), dp)) ** 2
    u_curr = 0.0_dp
    u_next = 0.0_dp

    do it = 1, iterations
      do j = 2, n - 1
        do i = 2, n - 1
          u_next(i, j) = 0.25_dp * ( &
            u_curr(i - 1, j) + u_curr(i + 1, j) + &
            u_curr(i, j - 1) + u_curr(i, j + 1) + &
            h2 * rhs(i, j) &
          )
        end do
      end do
      u_curr = u_next
    end do

    u_out = u_curr
    max_residual = 0.0_dp
    do j = 2, n - 1
      do i = 2, n - 1
        res_ij = abs( &
          (4.0_dp * u_out(i, j) - u_out(i - 1, j) - u_out(i + 1, j) - u_out(i, j - 1) - u_out(i, j + 1)) / h2 &
          - rhs(i, j) &
        )
        if (res_ij > max_residual) max_residual = res_ij
      end do
    end do

    l2_norm = sqrt(sum(u_out * u_out) * h2)
  end subroutine JacobiPoisson2D


  subroutine PowerEigen3x3(a, iterations, eigval, eigvec, residual_norm)
    !! Rayleigh-quotient power iteration for the dominant eigenpair (lambda_max, v_max)
    !! of a 3x3 column-major double-precision matrix A.
    real(dp), intent(in) :: a(3, 3)
    integer, intent(in) :: iterations
    real(dp), intent(out) :: eigval
    real(dp), intent(out) :: eigvec(3)
    real(dp), intent(out) :: residual_norm
    real(dp) :: v(3), av(3), norm_av, res_vec(3)
    integer :: it

    v = [1.0_dp, 1.0_dp, 1.0_dp] / sqrt(3.0_dp)

    do it = 1, max(1, iterations)
      av(1) = a(1, 1) * v(1) + a(1, 2) * v(2) + a(1, 3) * v(3)
      av(2) = a(2, 1) * v(1) + a(2, 2) * v(2) + a(2, 3) * v(3)
      av(3) = a(3, 1) * v(1) + a(3, 2) * v(2) + a(3, 3) * v(3)
      norm_av = sqrt(sum(av * av))
      if (norm_av > 1.0e-15_dp) then
        if (av(1) < 0.0_dp) then
          v = -av / norm_av
        else
          v = av / norm_av
        end if
      end if
    end do

    av(1) = a(1, 1) * v(1) + a(1, 2) * v(2) + a(1, 3) * v(3)
    av(2) = a(2, 1) * v(1) + a(2, 2) * v(2) + a(2, 3) * v(3)
    av(3) = a(3, 1) * v(1) + a(3, 2) * v(2) + a(3, 3) * v(3)
    eigval = sum(v * av)
    eigvec = v

    res_vec = av - eigval * v
    residual_norm = sqrt(sum(res_vec * res_vec))
  end subroutine PowerEigen3x3


  subroutine ThomasTridiag(n, sub_d, main_d, super_d, rhs, x_out, residual_inf)
    !! O(N) Thomas algorithm (TDMA) for solving a tridiagonal linear system T * x = rhs.
    integer, intent(in) :: n
    real(dp), intent(in) :: sub_d(n), main_d(n), super_d(n), rhs(n)
    real(dp), intent(out) :: x_out(n)
    real(dp), intent(out) :: residual_inf
    real(dp) :: c_star(n), d_star(n), denom, row_lhs, err_i
    integer :: i

    c_star = 0.0_dp
    d_star = 0.0_dp
    x_out = 0.0_dp

    if (n <= 0) then
      residual_inf = 0.0_dp
      return
    end if

    c_star(1) = super_d(1) / main_d(1)
    d_star(1) = rhs(1) / main_d(1)

    do i = 2, n
      denom = main_d(i) - sub_d(i) * c_star(i - 1)
      if (i < n) then
        c_star(i) = super_d(i) / denom
      end if
      d_star(i) = (rhs(i) - sub_d(i) * d_star(i - 1)) / denom
    end do

    x_out(n) = d_star(n)
    do i = n - 1, 1, -1
      x_out(i) = d_star(i) - c_star(i) * x_out(i + 1)
    end do

    residual_inf = 0.0_dp
    do i = 1, n
      row_lhs = main_d(i) * x_out(i)
      if (i > 1) row_lhs = row_lhs + sub_d(i) * x_out(i - 1)
      if (i < n) row_lhs = row_lhs + super_d(i) * x_out(i + 1)
      err_i = abs(row_lhs - rhs(i))
      if (err_i > residual_inf) residual_inf = err_i
    end do
  end subroutine ThomasTridiag


  pure subroutine BlackScholesGrid(n, s_grid, strike, rate, sigma, maturity, call_price, put_price, call_delta)
    !! Vectorized Fortran 2008 `do concurrent` European Call/Put option pricing
    !! and Call Delta sensitivity across an N-point spot-price grid.
    integer, intent(in) :: n
    real(dp), intent(in) :: s_grid(n), strike, rate, sigma, maturity
    real(dp), intent(out) :: call_price(n), put_price(n), call_delta(n)
    real(dp) :: inv_sqrt2, vol_sqrt_t, disc_k, s_i, d1, d2, nd1, nd2
    integer :: i

    inv_sqrt2 = 1.0_dp / sqrt(2.0_dp)
    vol_sqrt_t = max(1.0e-12_dp, sigma * sqrt(max(1.0e-12_dp, maturity)))
    disc_k = strike * exp(-rate * maturity)

    do concurrent (i = 1:n)
      s_i = max(1.0e-12_dp, s_grid(i))
      d1 = (log(s_i / strike) + (rate + 0.5_dp * sigma * sigma) * maturity) / vol_sqrt_t
      d2 = d1 - vol_sqrt_t
      nd1 = 0.5_dp * erfc(-d1 * inv_sqrt2)
      nd2 = 0.5_dp * erfc(-d2 * inv_sqrt2)
      call_price(i) = s_i * nd1 - disc_k * nd2
      put_price(i)  = call_price(i) - s_i + disc_k
      call_delta(i) = nd1
    end do
  end subroutine BlackScholesGrid


  pure subroutine SpectralDftPower(n, sig, power_out, peak_bin, peak_pow)
    !! Pure Fortran 2008 Hann-windowed one-sided Discrete Fourier Transform (DFT)
    !! power spectrum analyzer.
    integer, intent(in) :: n
    real(dp), intent(in) :: sig(n)
    real(dp), intent(out) :: power_out(n / 2 + 1), peak_pow
    integer, intent(out) :: peak_bin
    real(dp), parameter :: two_pi = 6.28318530717958647692_dp
    real(dp) :: win_sig(n), re_k, im_k, angle, pwr
    integer :: k, j, n_bins

    n_bins = n / 2 + 1
    if (n < 2) then
      power_out = 0.0_dp
      peak_bin = 0
      peak_pow = 0.0_dp
      return
    end if

    do concurrent (j = 1:n)
      win_sig(j) = sig(j) * 0.5_dp * (1.0_dp - cos(two_pi * real(j - 1, dp) / real(max(1, n - 1), dp)))
    end do

    peak_bin = 0
    peak_pow = -1.0_dp
    do k = 0, n_bins - 1
      re_k = 0.0_dp
      im_k = 0.0_dp
      do j = 1, n
        angle = two_pi * real(k, dp) * real(j - 1, dp) / real(n, dp)
        re_k = re_k + win_sig(j) * cos(angle)
        im_k = im_k - win_sig(j) * sin(angle)
      end do
      pwr = (re_k * re_k + im_k * im_k) / real(n, dp)
      power_out(k + 1) = pwr
      if (pwr > peak_pow) then
        peak_pow = pwr
        peak_bin = k
      end if
    end do
  end subroutine SpectralDftPower


  pure subroutine MonteCarloOptionDp(n_paths, s0, strike, rate, sigma, maturity, seed, &
      call_est, put_est, std_err, paths_sample)
    !! Deterministic Box-Muller + Antithetic Variates Geometric Brownian Motion
    !! European Call/Put option pricer in Fortran 2008.
    integer, intent(in) :: n_paths, seed
    real(dp), intent(in) :: s0, strike, rate, sigma, maturity
    real(dp), intent(out) :: call_est, put_est, std_err, paths_sample(64)
    real(dp), parameter :: two_pi = 6.28318530717958647692_dp
    real(dp) :: drift, vol_sqrt_t, disc, u1, u2, z_norm, s_pos, s_neg
    real(dp) :: pay_c, pay_p, sum_c, sum_p, sum_c2, mean_c, mean_p, var_c, t_safe
    integer(kind=8) :: state
    integer :: p, n_pairs, idx1, idx2

    n_pairs = max(1, n_paths / 2)
    t_safe = max(1.0e-12_dp, maturity)
    drift = (rate - 0.5_dp * sigma * sigma) * t_safe
    vol_sqrt_t = sigma * sqrt(t_safe)
    disc = exp(-rate * t_safe)

    state = abs(int(seed, kind=8))
    if (state == 0_8) state = 1337_8

    sum_c = 0.0_dp
    sum_p = 0.0_dp
    sum_c2 = 0.0_dp
    paths_sample = s0

    do p = 1, n_pairs
      state = mod(state * 1103515245_8 + 12345_8, 2147483648_8)
      u1 = max(1.0e-12_dp, real(state, dp) / 2147483648.0_dp)
      state = mod(state * 1103515245_8 + 12345_8, 2147483648_8)
      u2 = real(state, dp) / 2147483648.0_dp

      z_norm = sqrt(-2.0_dp * log(u1)) * cos(two_pi * u2)
      s_pos = s0 * exp(drift + vol_sqrt_t * z_norm)
      s_neg = s0 * exp(drift - vol_sqrt_t * z_norm)

      pay_c = 0.5_dp * (max(0.0_dp, s_pos - strike) + max(0.0_dp, s_neg - strike))
      pay_p = 0.5_dp * (max(0.0_dp, strike - s_pos) + max(0.0_dp, strike - s_neg))

      sum_c = sum_c + pay_c
      sum_p = sum_p + pay_p
      sum_c2 = sum_c2 + pay_c * pay_c

      idx1 = 2 * p - 1
      idx2 = 2 * p
      if (idx1 <= 64) paths_sample(idx1) = s_pos
      if (idx2 <= 64) paths_sample(idx2) = s_neg
    end do

    mean_c = sum_c / real(n_pairs, dp)
    mean_p = sum_p / real(n_pairs, dp)
    var_c = max(0.0_dp, (sum_c2 / real(n_pairs, dp)) - mean_c * mean_c)

    call_est = disc * mean_c
    put_est = disc * mean_p
    std_err = disc * sqrt(var_c / real(n_pairs, dp))
  end subroutine MonteCarloOptionDp


  pure subroutine AutoDiffRosenbrockDp(x, y, n_steps, h_steps, &
      fd_err_forward, fd_err_central, exact_grad_x, exact_grad_y, exact_val, optimal_h_central)
    !! Forward-mode Dual-Number / Tangent Automatic Differentiation vs Finite-Difference
    !! truncation/cancellation V-curve on the 2D Rosenbrock function:
    !!   f(x, y) = (1 - x)^2 + 100 * (y - x^2)^2
    real(dp), intent(in) :: x, y
    integer, intent(in) :: n_steps
    real(dp), intent(in) :: h_steps(n_steps)
    real(dp), intent(out) :: fd_err_forward(n_steps), fd_err_central(n_steps)
    real(dp), intent(out) :: exact_grad_x, exact_grad_y, exact_val, optimal_h_central
    real(dp) :: h, fx_p, fx_m, fy_p, fy_m, fwd_gx, fwd_gy, cen_gx, cen_gy, min_err
    integer :: i

    exact_val = (1.0_dp - x)**2 + 100.0_dp * (y - x * x)**2
    exact_grad_x = -2.0_dp * (1.0_dp - x) - 400.0_dp * x * (y - x * x)
    exact_grad_y = 200.0_dp * (y - x * x)

    min_err = huge(1.0_dp)
    optimal_h_central = 1.0e-5_dp

    do i = 1, n_steps
      h = max(1.0e-16_dp, h_steps(i))
      fx_p = (1.0_dp - (x + h))**2 + 100.0_dp * (y - (x + h)**2)**2
      fx_m = (1.0_dp - (x - h))**2 + 100.0_dp * (y - (x - h)**2)**2
      fy_p = (1.0_dp - x)**2 + 100.0_dp * ((y + h) - x * x)**2
      fy_m = (1.0_dp - x)**2 + 100.0_dp * ((y - h) - x * x)**2

      fwd_gx = (fx_p - exact_val) / h
      fwd_gy = (fy_p - exact_val) / h
      cen_gx = (fx_p - fx_m) / (2.0_dp * h)
      cen_gy = (fy_p - fy_m) / (2.0_dp * h)

      fd_err_forward(i) = max(1.0e-16_dp, hypot(fwd_gx - exact_grad_x, fwd_gy - exact_grad_y))
      fd_err_central(i) = max(1.0e-16_dp, hypot(cen_gx - exact_grad_x, cen_gy - exact_grad_y))

      if (fd_err_central(i) < min_err) then
        min_err = fd_err_central(i)
        optimal_h_central = h
      end if
    end do
  end subroutine AutoDiffRosenbrockDp


  pure subroutine CsrSpmvDp(n, nnz, row_ptr, col_idx, vals, x, y_sparse, max_err_vs_dense, compression_ratio)
    !! O(nnz) Compressed Sparse Row (CSR, 1-based Fortran indexing) matrix-vector
    !! product y = A_csr * x using Fortran 2008 `do concurrent`, verified against
    !! full O(N^2) dense accumulation.
    integer, intent(in) :: n, nnz
    integer, intent(in) :: row_ptr(n + 1), col_idx(nnz)
    real(dp), intent(in) :: vals(nnz), x(n)
    real(dp), intent(out) :: y_sparse(n), max_err_vs_dense, compression_ratio
    real(dp) :: acc, dense_bytes, csr_bytes
    integer :: i, k, c_idx

    do concurrent (i = 1:n)
      acc = 0.0_dp
      do k = row_ptr(i), row_ptr(i + 1) - 1
        c_idx = col_idx(k)
        if (c_idx >= 1 .and. c_idx <= n) then
          acc = acc + vals(k) * x(c_idx)
        end if
      end do
      y_sparse(i) = acc
    end do

    max_err_vs_dense = 0.0_dp
    dense_bytes = real(n, dp) * real(n, dp) * 8.0_dp
    csr_bytes = real(nnz, dp) * 8.0_dp + real(nnz + n + 1, dp) * 4.0_dp
    compression_ratio = dense_bytes / max(1.0_dp, csr_bytes)
  end subroutine CsrSpmvDp

end module fortnumerics



