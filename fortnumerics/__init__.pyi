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

fortnumerics: _FortNumericsModule
__all__: list[str]
