module fortnumerics
  !! Production Fortran 2008 numerical linear algebra, PDE stencil,
  !! composite quadrature, and floating-point stability routines for F2PY.
  use, intrinsic :: iso_fortran_env, only: sp => real32, dp => real64
  implicit none
  private
  public :: MatMulDp, Heat1DStep, SimpsonIntegrateDp, QuadraticRootsCompare, Rk4HarmonicStep, JacobiPoisson2D
  public :: PowerEigen3x3, ThomasTridiag, BlackScholesGrid, SpectralDftPower, MonteCarloOptionDp

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


  pure subroutine SpectralDftPower(n, signal, power_spectrum, dominant_bin, total_power, parseval_err)
    !! Pure Fortran 2008 `do concurrent` Discrete Fourier Transform (DFT) power spectrum
    !! analyzer with Parseval's theorem energy conservation verification.
    integer, intent(in) :: n
    real(dp), intent(in) :: signal(n)
    real(dp), intent(out) :: power_spectrum(n), total_power, parseval_err
    integer, intent(out) :: dominant_bin
    real(dp), parameter :: two_pi = 6.28318530717958647692_dp
    real(dp) :: re_k, im_k, angle, time_power, max_p
    integer :: k, j, half_n

    if (n <= 0) then
      dominant_bin = 0
      total_power = 0.0_dp
      parseval_err = 0.0_dp
      return
    end if

    do concurrent (k = 1:n)
      re_k = 0.0_dp
      im_k = 0.0_dp
      do j = 1, n
        angle = two_pi * real(k - 1, dp) * real(j - 1, dp) / real(n, dp)
        re_k = re_k + signal(j) * cos(angle)
        im_k = im_k - signal(j) * sin(angle)
      end do
      power_spectrum(k) = (re_k * re_k + im_k * im_k) / (real(n, dp) * real(n, dp))
    end do

    total_power = sum(power_spectrum)
    time_power = sum(signal * signal) / real(n, dp)
    parseval_err = abs(total_power - time_power)

    dominant_bin = 1
    max_p = -1.0_dp
    half_n = max(2, n / 2)
    do k = 2, half_n
      if (power_spectrum(k) > max_p) then
        max_p = power_spectrum(k)
        dominant_bin = k - 1
      end if
    end do
  end subroutine SpectralDftPower


  pure subroutine MonteCarloOptionDp(n_paths, s0, strike, rate, sigma, maturity, mc_call, mc_std_err, exact_bs_call, abs_err)
    !! Antithetic-variate quasi-Monte Carlo (Halton base-2/3 Box-Muller) European Call
    !! option pricer in Fortran 2008 compared against exact closed-form Black-Scholes.
    integer, intent(in) :: n_paths
    real(dp), intent(in) :: s0, strike, rate, sigma, maturity
    real(dp), intent(out) :: mc_call, mc_std_err, exact_bs_call, abs_err
    real(dp), parameter :: two_pi = 6.28318530717958647692_dp
    real(dp) :: drift, vol_sqrt_t, disc, u1, u2, z, s_plus, s_minus, payoff_pair
    real(dp) :: sum_payoff, sum_sq, mean_p, var_p, inv_sqrt2, d1, d2, nd1, nd2, f, r_val
    integer :: i, m, b

    m = max(10, n_paths)
    drift = (rate - 0.5_dp * sigma * sigma) * maturity
    vol_sqrt_t = max(1.0e-12_dp, sigma * sqrt(max(1.0e-12_dp, maturity)))
    disc = exp(-rate * maturity)

    sum_payoff = 0.0_dp
    sum_sq = 0.0_dp

    do i = 1, m
      ! Halton radical inverse base 2 for u1
      f = 0.5_dp
      r_val = 0.0_dp
      b = i
      do while (b > 0)
        r_val = r_val + f * real(mod(b, 2), dp)
        b = b / 2
        f = f * 0.5_dp
      end do
      u1 = max(1.0e-12_dp, min(1.0_dp - 1.0e-12_dp, r_val))

      ! Halton radical inverse base 3 for u2
      f = 1.0_dp / 3.0_dp
      r_val = 0.0_dp
      b = i
      do while (b > 0)
        r_val = r_val + f * real(mod(b, 3), dp)
        b = b / 3
        f = f / 3.0_dp
      end do
      u2 = max(1.0e-12_dp, min(1.0_dp - 1.0e-12_dp, r_val))

      z = sqrt(-2.0_dp * log(u1)) * cos(two_pi * u2)
      s_plus  = s0 * exp(drift + vol_sqrt_t * z)
      s_minus = s0 * exp(drift - vol_sqrt_t * z)
      payoff_pair = 0.5_dp * disc * (max(0.0_dp, s_plus - strike) + max(0.0_dp, s_minus - strike))
      sum_payoff = sum_payoff + payoff_pair
      sum_sq = sum_sq + payoff_pair * payoff_pair
    end do

    mean_p = sum_payoff / real(m, dp)
    var_p = max(0.0_dp, (sum_sq / real(m, dp)) - mean_p * mean_p)
    mc_call = mean_p
    mc_std_err = sqrt(var_p / real(m, dp))

    inv_sqrt2 = 1.0_dp / sqrt(2.0_dp)
    d1 = (log(max(1.0e-12_dp, s0) / strike) + (rate + 0.5_dp * sigma * sigma) * maturity) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    nd1 = 0.5_dp * erfc(-d1 * inv_sqrt2)
    nd2 = 0.5_dp * erfc(-d2 * inv_sqrt2)
    exact_bs_call = s0 * nd1 - strike * disc * nd2
    abs_err = abs(mc_call - exact_bs_call)
  end subroutine MonteCarloOptionDp

end module fortnumerics


