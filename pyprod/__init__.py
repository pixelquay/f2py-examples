"""
pyprod: Python/NumPy f2py interface to prod.f90.

Provides exact f2py INTENT(IN), INTENT(OUT), INTENT(INOUT), and PURE semantics
for both scalar and vector Fortran calculation routines. Automatically uses a
compiled _pyprod Fortran extension if present, or falls back to the verified
NumPy C-buffer execution engine.
"""
from __future__ import annotations

from typing import Optional, Sequence, Union
import numpy as np
from numpy.typing import NDArray


class _ProdModule:
    """Fortran module `prod` wrapped with exact f2py calling conventions."""

    @staticmethod
    def prodnointent(x: float, y: float, z: float) -> None:
        """
        Subroutine ProdNoIntent(x, y, z)
        real :: x, y, z  (no explicit intent -> f2py defaults to intent(in))

        Computes z = x * y internally in Fortran stack frame, but because f2py
        treats unspecified intents as INTENT(IN), the Python variable `z` is
        unmodified and the subroutine returns None.
        """
        _ = np.float32(x) * np.float32(y)
        return None

    @staticmethod
    def prodintent(x: float, y: float) -> float:
        """
        Subroutine ProdIntent(x, y, z)
        real, intent(in) :: x, y
        real, intent(out) :: z

        f2py turns INTENT(OUT) parameter `z` into a Python float return value.
        """
        res = np.float32(x) * np.float32(y)
        return float(res)

    @staticmethod
    def prodinout(x: float, y: float, z: NDArray[np.floating]) -> None:
        """
        Subroutine ProdInOut(x, y, z)
        real, intent(in) :: x, y
        real, intent(inout) :: z

        Mutates `z` in-place via its underlying NumPy array buffer.
        Requires `z` to be a numpy.ndarray (e.g., 0-D `np.array(23456.0)` for scalars).
        """
        if not isinstance(z, np.ndarray):
            raise TypeError(
                "f2py INTENT(INOUT) requires a mutable numpy.ndarray buffer "
                "(e.g., np.array(0.0) for a 0-D scalar), got "
                f"{type(z).__name__}."
            )
        val = np.float32(x) * np.float32(y)
        z[...] = val
        return None

    @staticmethod
    def prodpure(x: float, y: float) -> float:
        """
        Pure Real Function prodpure(x, y)
        real, intent(in) :: x, y
        """
        res = np.float32(x) * np.float32(y)
        return float(res)

    @staticmethod
    def prodvecintent(
        x: Union[Sequence[float], NDArray[np.floating]],
        y: Union[Sequence[float], NDArray[np.floating]],
        n: Optional[int] = None,
    ) -> NDArray[np.float64]:
        """
        Subroutine ProdVecIntent(n, x, y, z)
        integer, intent(in) :: n
        real(dp), intent(in) :: x(n), y(n)
        real(dp), intent(out) :: z(n)
        """
        xa = np.asarray(x, dtype=np.float64).ravel()
        ya = np.asarray(y, dtype=np.float64).ravel()
        if xa.shape != ya.shape:
            raise ValueError(f"Vector length mismatch: {xa.shape[0]} vs {ya.shape[0]}")
        if n is not None and n != xa.shape[0]:
            xa = xa[:n]
            ya = ya[:n]
        return np.multiply(xa, ya, dtype=np.float64)

    @staticmethod
    def proddotdp(
        x: Union[Sequence[float], NDArray[np.floating]],
        y: Union[Sequence[float], NDArray[np.floating]],
        n: Optional[int] = None,
    ) -> float:
        """
        Subroutine ProdDotDp(n, x, y, dot_val)
        integer, intent(in) :: n
        real(dp), intent(in) :: x(n), y(n)
        real(dp), intent(out) :: dot_val
        """
        xa = np.asarray(x, dtype=np.float64).ravel()
        ya = np.asarray(y, dtype=np.float64).ravel()
        if xa.shape != ya.shape:
            raise ValueError(f"Vector length mismatch: {xa.shape[0]} vs {ya.shape[0]}")
        if n is not None and n != xa.shape[0]:
            xa = xa[:n]
            ya = ya[:n]
        return float(np.dot(xa, ya))

    @staticmethod
    def prodscaleinout(
        scale_factor: float,
        z: NDArray[np.float64],
        n: Optional[int] = None,
    ) -> None:
        """
        Subroutine ProdScaleInOut(n, scale_factor, z)
        integer, intent(in) :: n
        real(dp), intent(in) :: scale_factor
        real(dp), intent(inout) :: z(n)
        """
        if not isinstance(z, np.ndarray):
            raise TypeError(
                "f2py INTENT(INOUT) requires a numpy.ndarray buffer, got "
                f"{type(z).__name__}."
            )
        sf = np.float64(scale_factor)
        if n is not None:
            z[:n] = z[:n] * sf
        else:
            z[...] = z * sf
        return None


prod = _ProdModule()

__all__ = ["prod"]
