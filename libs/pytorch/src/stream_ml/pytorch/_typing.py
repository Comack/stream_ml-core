"""Pytorch type hints."""

# STDLIB
from collections.abc import Mapping, MutableMapping

# THIRD-PARTY
from torch import Tensor as Array

__all__ = [
    "Array",
    # Parameters
    "FlatParsT",
    "MutableFlatParsT",
    # Data
    "DataT",
    "MutableDataT",
]


# TODO: define these from the stream_ml.core._typing versions

FlatParsT = Mapping[str, Array]
MutableFlatParsT = MutableMapping[str, Array]

DataT = Mapping[str, Array]
MutableDataT = MutableMapping[str, Array]
