"""Core feature."""

from __future__ import annotations

# STDLIB
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING

# THIRD-PARTY
import torch as xp

# LOCAL
from stream_ml.base import Model

if TYPE_CHECKING:
    # LOCAL
    from stream_ml._typing import Array, DataT, ParsT

__all__: list[str] = []


class CompositeModel(Model, Mapping[str, Model]):
    """Full Model.

    Parameters
    ----------
    models : Model
        Models.
    """

    def __init__(self, **models: Model) -> None:
        super().__init__()
        self._models = models

        # NOTE: don't need this in JAX
        for name, model in self._models.items():
            self.add_module(name=name, module=model)

    @property
    def param_names(self) -> dict[str, int]:  # type: ignore[override]
        """Parameter names."""
        return {k: v for d in self._models.values() for k, v in d.param_names.items()}

    # ===============================================================
    # Mapping

    def __getitem__(self, key: str) -> Model:
        return self._models[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._models)

    def __len__(self) -> int:
        return len(self._models)

    def __hash__(self) -> int:
        return hash(tuple(self.keys()))

    # ===============================================================
    # Statistics

    def ln_likelihood(self, pars: ParsT, data: DataT, *args: Array) -> Array:
        """Log likelihood.

        Just the log-sum-exp of the individual log-likelihoods.

        Parameters
        ----------
        pars : ParsT
            Parameters.
        data : DataT
            Data.
        args : Array
            Additional arguments.

        Returns
        -------
        Array
        """
        # (n_models, n_dat, 1)
        liks = xp.stack([xp.exp(model.ln_likelihood(pars, data, *args)) for model in self._models.values()])
        lik = liks.sum(dim=0)  # (n_dat, 1)
        return xp.log(lik)

    def ln_prior(self, pars: ParsT) -> Array:
        """Log prior.

        Parameters
        ----------
        pars : ParsT
            Parameters.

        Returns
        -------
        Array
        """
        return xp.stack([model.ln_prior(pars) for model in self._models.values()]).sum()

    # ========================================================================
    # ML

    def forward(self, *args: Array) -> Array:
        """Forward pass.

        Parameters
        ----------
        args : Array
            Input. Only uses the first argument.

        Returns
        -------
        Array
            fraction, mean, sigma
        """
        return xp.concat([model(*args) for model in self._models.values()], dim=1)
