"""Core feature."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

from dataclasses import dataclass, replace
import functools
import operator
from typing import TYPE_CHECKING, Any, overload

from stream_mapper.core._data import Data
from stream_mapper.core.typing import Array
from stream_mapper.core.utils.scale._api import DataScaler

if TYPE_CHECKING:
    from stream_mapper.core.typing import ArrayNamespace


@dataclass(frozen=True)
class CompoundDataScaler(DataScaler[Array]):
    """Compound scaler."""

    scalers: tuple[DataScaler[Array], ...]

    def __post_init__(self) -> None:
        # Check that all names are unique.
        names = set[str]()
        for scaler in self.scalers:
            if names.intersection(scaler.names):
                msg = f"duplicate name(s): {names.intersection(scaler.names)}"
                raise ValueError(msg)
            names.update(scaler.names)

        self.names: tuple[str, ...]
        object.__setattr__(
            self,
            "names",
            functools.reduce(operator.add, (s.names for s in self.scalers)),
        )

    # ---------------------------------------------------------------

    @overload
    def transform(
        self,
        data: Data[Array] | float,
        /,
        names: tuple[str, ...],
        *,
        xp: ArrayNamespace[Array] | None,
    ) -> Data[Array]:
        ...

    @overload
    def transform(
        self,
        data: Array | float,
        /,
        names: tuple[str, ...],
        *,
        xp: ArrayNamespace[Array] | None,
    ) -> Array:
        ...

    def transform(
        self,
        data: Data[Array] | Array | float,
        /,
        names: tuple[str, ...],
        *,
        xp: ArrayNamespace[Array] | None,
    ) -> Data[Array] | Array:
        """Scale features of X according to feature_range."""
        if xp is None:
            msg = "xp must be specified"
            raise ValueError(msg)

        is_data = isinstance(data, Data)
        data_: Data[Array] = (
            Data(xp.asarray(data), names=names) if not isinstance(data, Data) else data
        )

        xds: list[Array] = []
        v: Data[Array] | Array
        for scaler in self.scalers:
            ns = tuple(n for n in scaler.names if n in names)
            v = scaler.transform(data_[ns], names=ns, xp=xp)
            xds.append(v.array if isinstance(v, Data) else v)
        xd = xp.hstack(xds)

        return Data(xd, names=self.names) if is_data else xd

    # ---------------------------------------------------------------

    @overload
    def inverse_transform(
        self,
        data: Data[Array],
        /,
        names: tuple[str, ...],
        *,
        xp: ArrayNamespace[Array] | None,
    ) -> Data[Array]:
        ...

    @overload
    def inverse_transform(
        self,
        data: Array | float,
        /,
        names: tuple[str, ...],
        *,
        xp: ArrayNamespace[Array] | None,
    ) -> Array:
        ...

    def inverse_transform(
        self,
        data: Data[Array] | Array | float,
        /,
        names: tuple[str, ...],
        *,
        xp: ArrayNamespace[Array] | None,
    ) -> Data[Array] | Array:
        """Scale features of X according to feature_range."""
        if xp is None:
            msg = "xp must be specified"
            raise ValueError(msg)

        is_data = isinstance(data, Data)
        data_: Data[Array] = (
            Data(xp.asarray(data), names=names) if not isinstance(data, Data) else data
        )

        xds: list[Array] = []
        v: Data[Array] | Array
        for scaler in self.scalers:
            ns = tuple(n for n in scaler.names if n in names)
            v = scaler.inverse_transform(data_[ns], names=ns, xp=xp)
            xds.append(v.array if isinstance(v, Data) else v)
        xd = xp.hstack(xds)

        return Data(xd, names=self.names) if is_data else xd

    # ---------------------------------------------------------------

    def __getitem__(  # type: ignore[override]
        self, names: str | tuple[str, ...]
    ) -> CompoundDataScaler[Array] | DataScaler[Array]:
        """Get a subset DataScaler with the given names."""
        names_tuple = (names,) if isinstance(names, str) else names
        scalers = tuple(
            scaler[ns]
            for scaler in self.scalers
            if (ns := tuple(n for n in scaler.names if n in names_tuple))
        )
        return CompoundDataScaler[Array](scalers) if len(scalers) > 1 else scalers[0]

    # ---------------------------------------------------------------

    def astype(self, fmt: type[Array], /, **kwargs: Any) -> CompoundDataScaler[Array]:
        """Convert the data to a different format.

        Parameters
        ----------
        fmt : type
            The format to convert to.
        **kwargs : Any
            Additional keyword arguments.

        Returns
        -------
        DataScaler
        """
        return replace(
            self, scalers=tuple(s.astype(fmt, **kwargs) for s in self.scalers)
        )
