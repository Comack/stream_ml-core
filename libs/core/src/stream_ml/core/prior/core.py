"""Core feature."""

from __future__ import annotations

# STDLIB
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

# LOCAL
from stream_ml.core._typing import Array
from stream_ml.core.prior.base import PriorBase

if TYPE_CHECKING:
    # LOCAL
    from stream_ml.core.base import Model
    from stream_ml.core.params.core import Params

__all__: list[str] = []


@dataclass(frozen=True)
class Prior(PriorBase[Array]):
    """Prior."""

    logpdf_hook: Callable[[Params[Array], Model[Array], Array | None], Array]
    forward_hook: Callable[[Array, Model[Array]], Array]

    def logpdf(
        self,
        pars: Params[Array],
        model: Model[Array],
        current_lnpdf: Array | None = None,
        /,
    ) -> Array:
        """Evaluate the logpdf.

        This log-pdf is added to the current logpdf. So if you want to set the
        logpdf to a specific value, you can uses the `current_lnpdf` to set the
        output value such that ``current_lnpdf + logpdf = <want>``.

        Parameters
        ----------
        pars : Params[Array], position-only
            The parameters to evaluate the logpdf at.
        model : Model[Array], position-only
            The model for which evaluate the prior.
        current_lnpdf : Array | None, optional position-only
            The current logpdf, by default `None`. This is useful for setting
            the additive log-pdf to a specific value.

        Returns
        -------
        Array
            The logpdf.
        """
        return self.logpdf_hook(pars, model, current_lnpdf)

    def __call__(self, x: Array, model: Model[Array], /) -> Array:
        """Evaluate the forward step in the prior.

        Parameters
        ----------
        x : Array
            The input to evaluate the prior at.
        model : Model[Array]
            The model to evaluate the prior at.

        Returns
        -------
        Array
        """
        return self.forward_hook(x, model)
