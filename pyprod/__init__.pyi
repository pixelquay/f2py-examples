from typing import Optional, Sequence, Union
import numpy as np
from numpy.typing import NDArray

class _ProdModule:
    @staticmethod
    def prodnointent(x: float, y: float, z: float) -> None: ...
    @staticmethod
    def prodintent(x: float, y: float) -> float: ...
    @staticmethod
    def prodinout(x: float, y: float, z: NDArray[np.floating]) -> None: ...
    @staticmethod
    def prodpure(x: float, y: float) -> float: ...
    @staticmethod
    def prodvecintent(
        x: Union[Sequence[float], NDArray[np.floating]],
        y: Union[Sequence[float], NDArray[np.floating]],
        n: Optional[int] = None,
    ) -> NDArray[np.float64]: ...
    @staticmethod
    def proddotdp(
        x: Union[Sequence[float], NDArray[np.floating]],
        y: Union[Sequence[float], NDArray[np.floating]],
        n: Optional[int] = None,
    ) -> float: ...
    @staticmethod
    def prodscaleinout(
        scale_factor: float,
        z: NDArray[np.float64],
        n: Optional[int] = None,
    ) -> None: ...

prod: _ProdModule
