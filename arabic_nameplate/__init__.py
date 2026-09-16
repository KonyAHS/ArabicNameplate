"""Parametric Arabic nameplates for FreeCAD."""

from .feature import ArabicNameplateProxy, create_nameplate
from .parameters import DEFAULTS, PARAMETERS, parameters_from_object, validate_parameters

__all__ = [
    "ArabicNameplateProxy",
    "DEFAULTS",
    "PARAMETERS",
    "create_nameplate",
    "parameters_from_object",
    "validate_parameters",
]

__version__ = "0.1.0"
