"""Core feature."""

from __future__ import annotations

from abc import ABCMeta
from dataclasses import KW_ONLY, InitVar, dataclass, field, fields
from functools import reduce
from math import inf
import textwrap
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Protocol, TypeVar, cast

from stream_ml.core.api import Model
from stream_ml.core.params import ParamBounds, Params, freeze_params, set_param
from stream_ml.core.params.bounds import ParamBoundsField
from stream_ml.core.params.names import ParamNamesField
from stream_ml.core.prior.bounds import NoBounds
from stream_ml.core.setup_package import WEIGHT_NAME, CompiledShim
from stream_ml.core.typing import Array, ArrayNamespace, BoundsT, NNModel, NNNamespace
from stream_ml.core.utils.compat import array_at
from stream_ml.core.utils.frozen_dict import FrozenDict, FrozenDictField
from stream_ml.core.utils.funcs import within_bounds

__all__: list[str] = []


if TYPE_CHECKING:
    from stream_ml.core.data import Data
    from stream_ml.core.prior.base import PriorBase

    Self = TypeVar("Self", bound="ModelBase[Array, NNModel]")  # type: ignore[valid-type]  # noqa: E501


#####################################################################
# PARAMETERS


class NNNamespaceMap(Protocol):
    """Protocol for mapping array namespaces to NN namespaces."""

    def __getitem__(self, key: ArrayNamespace[Array]) -> NNNamespace[NNModel, Array]:
        """Get item."""
        ...

    def __setitem__(
        self, key: ArrayNamespace[Array], value: NNNamespace[NNModel, Array]
    ) -> None:
        """Set item."""
        ...


NN_NAMESPACE = cast(NNNamespaceMap, {})


#####################################################################


@dataclass(frozen=True, slots=True)
class NNField(Generic[NNModel]):
    """Dataclass descriptor for attached nn.

    Parameters
    ----------
    default : NNModel | None, optional
        Default value, by default `None`.

        - `NNModel` : a value.
        - `None` : defer setting a value until model init.
    """

    default: NNModel | None = None
    _name: str = field(default="")

    def __set_name__(self, owner: type, name: str) -> None:
        object.__setattr__(self, "_name", "_" + name)

    def __get__(
        self, model: ModelBase[Array, NNModel] | None, model_cls: Any
    ) -> NNModel | None:
        if model is not None:
            return cast("NNModel", getattr(model, self._name))
        return self.default

    def __set__(
        self,
        model: ModelBase[Array, NNModel],
        value: NNModel | None,
    ) -> None:
        # Call the _net_init_default hook. This can be Any | None
        # First need to ensure that the array and nn namespaces are set.
        net = model._net_init_default() if value is None else value

        if net is None:
            msg = "must provide a wrapped neural network."
            raise ValueError(msg)

        object.__setattr__(model, self._name, net)


@dataclass(unsafe_hash=True)
class ModelBase(Model[Array, NNModel], CompiledShim, metaclass=ABCMeta):
    """Single-model base class.

    Parameters
    ----------
    net : NNField[NNModel], keyword-only
        The neural network.

    array_namespace : ArrayNamespace[Array], keyword-only
        The array namespace.

    coord_names : tuple[str, ...], keyword-only
        The names of the coordinates, not including the 'independent' variable.
        E.g. for independent variable 'phi1' this might be ('phi2', 'prlx',
        ...).
    coord_bounds : Mapping[str, tuple[float, float]], keyword-only
        The bounds on the coordinates. If not provided, the bounds are
        (-inf, inf) for all coordinates.

    param_names : `~stream_ml.core.params.ParamNames`, keyword-only
        The names of the parameters. Parameters dependent on the coordinates are
        grouped by the coordinate name.
        E.g. ('weight', ('phi1', ('mu', 'sigma'))).
    param_bounds : `~stream_ml.core.params.ParamBounds`, keyword-only
        The bounds on the parameters.

    name : str or None, optional keyword-only
        The (internal) name of the model, e.g. 'stream' or 'background'. Note
        that this can be different from the name of the model when it is used in
        a mixture model (see :class:`~stream_ml.core.core.MixtureModel`).
    """

    net: NNField[NNModel] = NNField(default=None)

    _: KW_ONLY
    array_namespace: InitVar[ArrayNamespace[Array]]
    name: str | None = None  # the name of the model

    indep_coord_names: tuple[str, ...] = ("phi1",)
    coord_names: tuple[str, ...]
    param_names: ParamNamesField = ParamNamesField()

    # Bounds on the coordinates and parameters.
    coord_bounds: FrozenDictField[str, BoundsT] = FrozenDictField(FrozenDict())
    param_bounds: ParamBoundsField[Array] = ParamBoundsField[Array](ParamBounds())

    priors: tuple[PriorBase[Array], ...] = ()

    DEFAULT_BOUNDS: ClassVar = NoBounds()  # TODO: [PriorBounds[Any]]

    def __new__(  # noqa: D102
        cls: type[Self],
        *args: Any,  # noqa: ARG003
        array_namespace: ArrayNamespace[Array],
        **kwargs: Any,  # noqa: ARG003
    ) -> Self:
        # Create the model instance.
        # TODO: Model.__new__ over objects.__new__ is a mypyc hack.
        self = Model.__new__(cls)

        # Ensure that the array and nn namespaces are available to the dataclass
        # descriptor fields.
        self._array_namespace_ = array_namespace
        self._nn_namespace_ = NN_NAMESPACE[array_namespace]

        return self

    def __post_init__(self, array_namespace: ArrayNamespace[Array]) -> None:
        """Post-init validation."""
        super().__post_init__(array_namespace=array_namespace)
        self._mypyc_init_descriptor()  # TODO: Remove this when mypyc is fixed.

        # Validate the param_names
        if not self.param_names:
            msg = "param_names must be specified"
            raise ValueError(msg)

        # Make coord bounds if not provided
        crnt_cbs = dict(self.coord_bounds)
        cbs = {n: crnt_cbs.pop(n, (-inf, inf)) for n in self.coord_names}
        if crnt_cbs:  # Error if there are extra keys
            msg = f"coord_bounds contains invalid keys {crnt_cbs.keys()}."
            raise ValueError(msg)
        self.coord_bounds = FrozenDict(cbs)

    def _net_init_default(self) -> Any | None:
        return None

    # ========================================================================

    def unpack_params_from_arr(self, p_arr: Array) -> Params[Array]:
        """Unpack parameters into a dictionary.

        This function takes a parameter array and unpacks it into a dictionary
        with the parameter names as keys.

        Parameters
        ----------
        p_arr : Array
            Parameter array.

        Returns
        -------
        Params[Array]
        """
        pars: dict[str, Array | dict[str, Array]] = {}
        for i, k in enumerate(self.param_names.flats):
            set_param(pars, k, p_arr[:, i : i + 1])
        return freeze_params(pars)

    # ========================================================================
    # Statistics

    def _ln_prior_coord_bnds(self, mpars: Params[Array], data: Data[Array]) -> Array:
        """Elementwise log prior for coordinate bounds.

        Parameters
        ----------
        mpars : Params[Array], positional-only
            Model parameters. Note that these are different from the ML
            parameters.
        data : Data[Array]
            Data.

        Returns
        -------
        Array
            Zero everywhere except where the data are outside the
            coordinate bounds, where it is -inf.
        """
        lnp = self.xp.zeros_like(mpars[(WEIGHT_NAME,)])
        where = reduce(
            self.xp.logical_or,
            (~within_bounds(data[k], *v) for k, v in self.coord_bounds.items()),
        )
        return array_at(lnp, where).set(-self.xp.inf)

    def ln_prior(
        self, mpars: Params[Array], data: Data[Array], current_lnp: Array | None = None
    ) -> Array:
        """Log prior.

        Parameters
        ----------
        mpars : Params[Array], positional-only
            Model parameters. Note that these are different from the ML
            parameters.
        data : Data[Array]
            Data (phi1, phi2).
        current_lnp : Array | None, optional
            Current value of the log prior, by default `None`.

        Returns
        -------
        Array
        """
        lnp: Array = self.xp.zeros(()) if current_lnp is None else current_lnp

        # Coordinate Bounds
        lnp = lnp + self._ln_prior_coord_bnds(mpars, data)
        # Parameter Bounds
        for bounds in self.param_bounds.flatvalues():
            lnp = lnp + bounds.logpdf(mpars, data, self, lnp, xp=self.xp)
        # Priors
        for prior in self.priors:
            lnp = lnp + prior.logpdf(mpars, data, self, lnp, xp=self.xp)

        return lnp

    # ========================================================================
    # ML

    def _forward_priors(self, out: Array, data: Data[Array]) -> Array:
        """Forward pass.

        Parameters
        ----------
        out : Array
            Input.
        data : Data[Array]
            Data.

        Returns
        -------
        Array
            Same as input.
        """
        # Parameter bounds
        for bnd in self.param_bounds.flatvalues():
            out = bnd(out, data, self)

        # Other priors
        # TODO: a better way to do the order of the priors.
        for prior in self.priors:
            out = prior(out, data, self)
        return out

    # ========================================================================
    # Misc

    def __str__(self) -> str:
        """Return string representation."""
        s = f"{self.__class__.__name__}(\n"
        s += "\n".join(
            textwrap.indent(f"{f.name}: {getattr(self, f.name)!s}", prefix="\t")
            for f in fields(self)
        )
        s += "\n)"
        return s
