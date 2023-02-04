"""Core feature."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TypeVar, cast, overload

from stream_ml.core.params.names import LEN_NAME_TUPLE
from stream_ml.core.utils.frozen_dict import FrozenDict

__all__: list[str] = []


V = TypeVar("V")


#####################################################################


class Params(FrozenDict[str, V | FrozenDict[str, V]]):
    """Parameter dictionary."""

    def __init__(
        self,
        m: Mapping[str, V | Mapping[str, V]] = {},
        /,
        **kwargs: V | Mapping[str, V],
    ) -> None:
        # Freeze sub-dicts
        d: dict[str, V | FrozenDict[str, V]] = {
            k: v if not isinstance(v, Mapping) else FrozenDict[str, V](v)
            for k, v in dict(m, **kwargs).items()
        }
        super().__init__(d, __unsafe_skip_copy__=True)

    # -----------------------------------------------------

    @overload
    def __getitem__(self, key: str) -> V | FrozenDict[str, V]:
        ...

    @overload
    def __getitem__(self, key: tuple[str]) -> V:
        ...

    @overload
    def __getitem__(self, key: tuple[str, str]) -> V:
        ...

    def __getitem__(
        self, key: str | tuple[str] | tuple[str, str]
    ) -> V | FrozenDict[str, V]:
        if isinstance(key, str):
            value = self._dict[key]
        elif len(key) == 1:
            value = self._dict[key[0]]
        elif len(key) == LEN_NAME_TUPLE:
            key = cast("tuple[str, str]", key)  # TODO: remove cast
            cm = self._dict[key[0]]
            if not isinstance(cm, Mapping):
                raise KeyError(str(key))
            value = cm[key[1]]
        else:
            raise KeyError(str(key))
        return value

    def unfreeze(self) -> dict[str, V | dict[str, V]]:  # type: ignore[override]
        """Unfreeze the parameters."""
        return unfreeze_params(self)

    # =========================================================================
    # Flat

    def flatitems(self) -> Iterable[tuple[str, V]]:
        """Flat items."""
        for k, v in self.items():
            if not isinstance(v, Mapping):
                yield k, v
            else:
                for k2, v2 in v.items():
                    yield f"{k}_{k2}", v2

    def flatkeys(self) -> Iterable[str]:
        """Flat keys."""
        for k, _ in self.flatitems():
            yield k

    def flatvalues(self) -> Iterable[V]:
        """Flat values."""
        for _, v in self.flatitems():
            yield v

    # =========================================================================

    def get_prefixed(self, prefix: str) -> Params[V]:
        """Get the keys starting with the prefix, stripped of that prefix."""
        prefix = prefix + "." if not prefix.endswith(".") else prefix
        lp = len(prefix)
        return type(self)({k[lp:]: v for k, v in self.items() if k.startswith(prefix)})

    def add_prefix(self, prefix: str, /) -> Params[V]:
        """Add the prefix to the keys."""
        return type(self)({f"{prefix}{k}": v for k, v in self.items()})


#####################################################################


def freeze_params(m: Mapping[str, V | Mapping[str, V]], /) -> Params[V]:
    """Freeze a mapping of parameters."""
    return Params(m)


def unfreeze_params(
    pars: Params[V],
    /,
) -> dict[str, V | dict[str, V]]:
    """Unfreeze a mapping of parameters."""
    return {k: v if not isinstance(v, Mapping) else dict(v) for k, v in pars.items()}


# -----------------------------------------------------


@overload
def set_param(
    m: dict[str, V | dict[str, V]],
    /,
    key: str,
    value: V | dict[str, V],
) -> None:
    ...


@overload
def set_param(
    m: dict[str, V | dict[str, V]],
    /,
    key: tuple[str],
    value: V | dict[str, V],
) -> None:
    ...


@overload
def set_param(
    m: dict[str, V | dict[str, V]],
    /,
    key: tuple[str, str],
    value: V,
) -> None:
    ...


def set_param(
    m: dict[str, V | dict[str, V]],
    /,
    key: str | tuple[str] | tuple[str, str],
    value: V | dict[str, V],
) -> None:
    """Set a parameter in-place."""
    if isinstance(key, str):
        m[key] = value
    elif len(key) == 1:
        m[key[0]] = value
    else:
        key = cast("tuple[str, str]", key)  # TODO: remove cast
        if key[0] not in m:
            m[key[0]] = {}
        if not isinstance((cm := m[key[0]]), dict):
            raise KeyError(str(key))
        cm[key[1]] = value  # type: ignore[assignment]

    return
