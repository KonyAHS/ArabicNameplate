"""Shared parameter schema and FreeCAD-independent validation.

The UI and the FeaturePython proxy both consume :data:`PARAMETERS`.  Keeping the
schema here makes saved objects, task panels and headless scripts use identical
names and defaults.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PARAMETERS: list[dict[str, Any]] = [
    {"name": "Text", "type": "string", "label": "Text", "group": "Text", "default": "مرحباً", "help": "Arabic or mixed-direction text to turn into a nameplate."},
    {"name": "FontFamily", "type": "font", "label": "Font family", "group": "Text", "default": "Noto Sans Arabic", "help": "A system font family. A compatible installed font is used as fallback when needed."},
    {"name": "FontSize", "type": "length", "label": "Font size", "group": "Text", "default": 20.0, "help": "Font em size in millimetres.", "min": 0.1, "max": 1000.0, "step": 1.0},
    {"name": "Bold", "type": "bool", "label": "Bold", "group": "Text", "default": False, "help": "Request the bold face of the selected font."},
    {"name": "Italic", "type": "bool", "label": "Italic", "group": "Text", "default": False, "help": "Request the italic face of the selected font."},
    {"name": "Alignment", "type": "enum", "label": "Alignment", "group": "Text", "default": "Center", "choices": ["Left", "Center", "Right"], "help": "Horizontal alignment for multiple lines."},
    {"name": "Direction", "type": "enum", "label": "Text direction", "group": "Text", "default": "Auto", "choices": ["Auto", "RTL", "LTR"], "help": "Detect direction from the text or force right-to-left/left-to-right layout."},
    {"name": "LineSpacing", "type": "float", "label": "Line spacing", "group": "Text", "default": 1.2, "help": "Distance between baselines as a multiple of font size.", "min": 0.2, "max": 5.0, "step": 0.05},
    {"name": "TextHeight", "type": "length", "label": "Letter height", "group": "Text", "default": 3.0, "help": "Extrusion height of the raised letter faces.", "min": 0.01, "max": 1000.0, "step": 0.1},
    {"name": "OutlineWidth", "type": "length", "label": "Outline width", "group": "Outline", "default": 1.2, "help": "Horizontal offset around each letter. Set to zero to disable the outline.", "min": 0.0, "max": 100.0, "step": 0.1},
    {"name": "OutlineHeight", "type": "length", "label": "Outline height", "group": "Outline", "default": 1.2, "help": "Extrusion height of the wider lower outline.", "min": 0.01, "max": 1000.0, "step": 0.1},
    {"name": "OutlineJoin", "type": "enum", "label": "Outline corners", "group": "Outline", "default": "Round", "choices": ["Round", "Miter", "Bevel"], "help": "Corner treatment used when offsetting letter outlines."},
    {"name": "BaseStyle", "type": "enum", "label": "Base", "group": "Base", "default": "None", "choices": ["None", "Contour", "Rounded rectangle"], "help": "Optional backing plate behind the text."},
    {"name": "BaseMargin", "type": "length", "label": "Base margin", "group": "Base", "default": 3.0, "help": "Clearance from the text or outline to the base edge.", "min": 0.0, "max": 1000.0, "step": 0.5},
    {"name": "BaseHeight", "type": "length", "label": "Base height", "group": "Base", "default": 2.0, "help": "Extrusion height of the backing plate.", "min": 0.01, "max": 1000.0, "step": 0.1},
    {"name": "CornerRadius", "type": "length", "label": "Corner radius", "group": "Base", "default": 3.0, "help": "Corner radius of a rounded rectangular base.", "min": 0.0, "max": 1000.0, "step": 0.5},
    {"name": "ConnectionMode", "type": "enum", "label": "Connection method", "group": "Connections", "default": "Bridges", "choices": ["None", "Bridges", "Baseline"], "help": "Join separate letters with short bridges or a continuous baseline."},
    {"name": "ConnectionScope", "type": "enum", "label": "Connection scope", "group": "Connections", "default": "All", "choices": ["All", "Words"], "help": "Connect the whole sign or keep words as separate printable masses."},
    {"name": "BridgeWidth", "type": "length", "label": "Bridge width", "group": "Connections", "default": 1.2, "help": "Minimum width of generated letter connectors.", "min": 0.01, "max": 1000.0, "step": 0.1},
    {"name": "BridgeHeight", "type": "length", "label": "Bridge height", "group": "Connections", "default": 1.2, "help": "Extrusion height of bridges or the baseline connector.", "min": 0.01, "max": 1000.0, "step": 0.1},
    {"name": "BaselineOffset", "type": "length", "label": "Baseline offset", "group": "Connections", "default": 0.0, "help": "Vertical offset of the baseline connector from the text baseline.", "min": -1000.0, "max": 1000.0, "step": 0.1},
    {"name": "MinFeature", "type": "length", "label": "Minimum feature", "group": "Manufacturing", "default": 0.4, "help": "Warn about details thinner than this 3D-printing threshold. Zero disables the check.", "min": 0.0, "max": 100.0, "step": 0.1},
    {"name": "CurveTolerance", "type": "length", "label": "Curve tolerance", "group": "Manufacturing", "default": 0.05, "help": "Maximum curve approximation error; lower values create denser outlines.", "min": 0.001, "max": 10.0, "step": 0.01},
]

DEFAULTS: dict[str, Any] = {item["name"]: item["default"] for item in PARAMETERS}
PARAMETER_NAMES = frozenset(DEFAULTS)


def _plain_value(value: Any) -> Any:
    """Return the numeric value of a FreeCAD Quantity without importing FreeCAD."""

    if hasattr(value, "Value"):
        return value.Value
    return value


def parameters_from_object(obj: Any) -> dict[str, Any]:
    """Extract geometry-ready plain values from a FreeCAD feature or mapping."""

    result: dict[str, Any] = {}
    is_mapping = isinstance(obj, Mapping)
    for spec in PARAMETERS:
        name = spec["name"]
        if is_mapping:
            value = obj.get(name, spec["default"])
        else:
            value = getattr(obj, name, spec["default"])
        value = _plain_value(value)
        if spec["type"] in {"length", "float"}:
            try:
                value = float(value)
            except (TypeError, ValueError):
                pass
        elif spec["type"] == "bool":
            value = bool(value)
        elif spec["type"] in {"string", "font", "enum"}:
            value = str(value)
        result[name] = value
    return result


def validate_parameters(params: Mapping[str, Any]) -> list[str]:
    """Return human-readable validation errors; an empty list means valid."""

    errors: list[str] = []
    for spec in PARAMETERS:
        name = spec["name"]
        label = spec["label"]
        value = _plain_value(params.get(name, spec["default"]))
        kind = spec["type"]

        if kind in {"string", "font"}:
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} cannot be empty.")
            continue
        if kind == "bool":
            if not isinstance(value, bool):
                errors.append(f"{label} must be true or false.")
            continue
        if kind == "enum":
            if value not in spec["choices"]:
                choices = ", ".join(spec["choices"])
                errors.append(f"{label} must be one of: {choices}.")
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            errors.append(f"{label} must be a number.")
            continue
        if number != number or number in (float("inf"), float("-inf")):
            errors.append(f"{label} must be a finite number.")
            continue
        if "min" in spec and number < spec["min"]:
            errors.append(f"{label} must be at least {spec['min']:g}.")
        if "max" in spec and number > spec["max"]:
            errors.append(f"{label} must be at most {spec['max']:g}.")

    return errors
