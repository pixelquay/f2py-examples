from typing import Sequence, Tuple, Union
import numpy as np
from numpy.typing import NDArray

class _FortNumericsModule:
    @staticmethod
    def matmuldp(
        a: Union[Sequence[Sequence[float]], NDArray[np.floating]],
        b: Union[Sequence[Sequence[float]], NDArray[np.floating]],
    ) -> NDArray[np.float64]: ...
    @staticmethod
    def heat1dstep(
        steps: int,
        alpha: float,
        dx: float,
        dt: float,
        u_init: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float, float]: ...
    @staticmethod
    def simpsonintegratedp(
        dx: float,
        y: Union[Sequence[float], NDArray[np.floating]],
    ) -> float: ...
    @staticmethod
    def quadraticrootscompare(
        a: float,
        b: float,
        c: float,
    ) -> Tuple[float, float, float, float, float]: ...
    @staticmethod
    def rk4harmonicstep(
        steps: int,
        dt: float,
        omega0: float,
        zeta: float,
        x0: float,
        v0: float,
    ) -> Tuple[NDArray[np.float64], NDArray[np.float64], float]: ...
    @staticmethod
    def jacobipoisson2d(
        iterations: int,
        rhs: Union[Sequence[Sequence[float]], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float, float]: ...
    @staticmethod
    def powereigen3x3(
        a: Union[Sequence[Sequence[float]], NDArray[np.floating]],
        iterations: int,
    ) -> Tuple[float, NDArray[np.float64], float]: ...
    @staticmethod
    def thomastridiag(
        sub_d: Union[Sequence[float], NDArray[np.floating]],
        main_d: Union[Sequence[float], NDArray[np.floating]],
        super_d: Union[Sequence[float], NDArray[np.floating]],
        rhs: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float]: ...
    @staticmethod
    def blackscholesgrid(
        s_grid: Union[Sequence[float], NDArray[np.floating]],
        strike: float,
        rate: float,
        sigma: float,
        maturity: float,
    ) -> Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]: ...
    @staticmethod
    def spectraldftpower(
        sig: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], int, float]: ...
    @staticmethod
    def montecarlooptiondp(
        n_paths: int,
        s0: float,
        strike: float,
        rate: float,
        sigma: float,
        maturity: float,
        seed: int = 42,
    ) -> Tuple[float, float, float, NDArray[np.float64]]: ...
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
    ]: ...
    @staticmethod
    def csrspmvdp(
        row_ptr: Union[Sequence[int], NDArray[np.integer]],
        col_idx: Union[Sequence[int], NDArray[np.integer]],
        vals: Union[Sequence[float], NDArray[np.floating]],
        x: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float, float]: ...
    @staticmethod
    def cranknicolson1d(
        steps: int,
        alpha: float,
        dx: float,
        dt: float,
        u_init: Union[Sequence[float], NDArray[np.floating]],
    ) -> Tuple[NDArray[np.float64], float, float]: ...
    @staticmethod
    def newtonsystem2d(
        x0: float,
        y0: float,
        r_circle: float = 1.0,
        max_iters: int = 15,
        tol: float = 1e-14,
    ) -> Tuple[float, float, NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], int]: ...

fortnumerics: _FortNumericsModule
__all__: list[str]
