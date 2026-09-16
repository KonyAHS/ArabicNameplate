"""FreeCAD FeaturePython integration for parametric nameplates."""

from __future__ import annotations

from typing import Any

from .parameters import DEFAULTS, PARAMETER_NAMES, PARAMETERS, parameters_from_object, validate_parameters


_PROPERTY_TYPES = {
    "string": "App::PropertyString",
    "font": "App::PropertyString",
    "length": "App::PropertyLength",
    "float": "App::PropertyFloat",
    "bool": "App::PropertyBool",
    "enum": "App::PropertyEnumeration",
}


def _add_property(obj: Any, type_name: str, name: str, group: str, help_text: str) -> bool:
    if name not in getattr(obj, "PropertiesList", []):
        obj.addProperty(type_name, name, group, help_text)
        return True
    return False


def _empty_shape() -> Any:
    import Part  # type: ignore

    return Part.Shape()


class ArabicNameplateProxy:
    """Persistent parametric proxy; all user inputs stay editable after creation."""

    Type = "ArabicNameplate"

    def __init__(self, obj: Any | None = None) -> None:
        if obj is not None:
            self.attach(obj)

    def attach(self, obj: Any) -> None:
        obj.Proxy = self
        for spec in PARAMETERS:
            name = spec["name"]
            property_type = _PROPERTY_TYPES[spec["type"]]
            if spec["type"] == "length" and spec.get("min", 0.0) < 0.0:
                property_type = "App::PropertyDistance"
            added = _add_property(obj, property_type, name, spec["group"], spec["help"])
            if spec["type"] == "enum":
                previous = str(getattr(obj, name, spec["default"]))
                setattr(obj, name, list(spec["choices"]))
                setattr(obj, name, previous if previous in spec["choices"] else spec["default"])
            elif added:
                setattr(obj, name, spec["default"])

        _add_property(obj, "Part::PropertyPartShape", "Shape", "Output", "Generated printable geometry.")
        added_status = _add_property(obj, "App::PropertyString", "Status", "Output", "Current generation status.")
        added_error = _add_property(obj, "App::PropertyString", "LastError", "Output", "Most recent generation error.")
        added_warnings = _add_property(obj, "App::PropertyStringList", "Warnings", "Output", "Non-fatal printability and geometry warnings.")
        added_solids = _add_property(obj, "App::PropertyInteger", "SolidCount", "Output", "Number of solids in the generated shape.")
        _add_property(obj, "App::PropertyLength", "OverallWidth", "Output", "Generated X dimension.")
        _add_property(obj, "App::PropertyLength", "OverallHeight", "Output", "Generated Y dimension.")
        _add_property(obj, "App::PropertyLength", "OverallDepth", "Output", "Generated Z dimension.")
        added_fonts = _add_property(obj, "App::PropertyStringList", "ResolvedFontFamilies", "Output", "Font families actually used for the shaped text.")
        for name in ("Status", "LastError", "Warnings", "SolidCount", "OverallWidth", "OverallHeight", "OverallDepth", "ResolvedFontFamilies"):
            obj.setEditorMode(name, 1)
        if added_status:
            obj.Status = "Ready to recompute"
        if added_error:
            obj.LastError = ""
        if added_warnings:
            obj.Warnings = []
        if added_solids:
            obj.SolidCount = 0
        if added_fonts:
            obj.ResolvedFontFamilies = []

    def onDocumentRestored(self, obj: Any) -> None:  # noqa: N802 - FreeCAD callback
        """Migrate old saved objects by adding any properties introduced later."""

        self.attach(obj)

    def execute(self, obj: Any) -> None:
        """Rebuild the shape. Any failure clears the previous, now-stale result."""

        placement = getattr(obj, "Placement", None)
        if placement is not None and hasattr(placement, "copy"):
            placement = placement.copy()
        try:
            obj.Shape = _empty_shape()
            obj.SolidCount = 0
            obj.OverallWidth = 0.0
            obj.OverallHeight = 0.0
            obj.OverallDepth = 0.0
            obj.Warnings = []
            obj.ResolvedFontFamilies = []
            params = parameters_from_object(obj)
            errors = validate_parameters(params)
            if errors:
                raise ValueError(" ".join(errors))

            # Geometry has optional Qt/font dependencies and must remain importable only
            # inside a running FreeCAD process.
            from .geometry import build_nameplate

            result = build_nameplate(params)
            if not isinstance(result, dict) or result.get("shape") is None:
                raise RuntimeError("The geometry builder returned no shape.")
            shape = result["shape"]
            if hasattr(shape, "isNull") and shape.isNull():
                raise RuntimeError("The generated shape is empty.")
            if hasattr(shape, "isValid") and not shape.isValid():
                raise RuntimeError("The generated shape is invalid.")
            solids = getattr(shape, "Solids", [])
            if not solids:
                raise RuntimeError("The generated shape contains no solids.")
            obj.Shape = shape
            warnings = [str(item) for item in result.get("warnings", [])]
            obj.Warnings = warnings
            obj.ResolvedFontFamilies = [str(item) for item in result.get("font_families", [])]
            obj.SolidCount = int(result.get("solid_count", len(solids)))
            bounds = getattr(shape, "BoundBox", None)
            if bounds is not None:
                obj.OverallWidth = float(bounds.XLength)
                obj.OverallHeight = float(bounds.YLength)
                obj.OverallDepth = float(bounds.ZLength)
            obj.LastError = ""
            obj.Status = "Generated with warnings" if warnings else "Generated"
        except Exception as exc:  # FreeCAD reports details through persistent properties.
            try:
                obj.Shape = _empty_shape()
            except Exception:
                pass
            obj.SolidCount = 0
            obj.LastError = f"{type(exc).__name__}: {exc}"
            obj.Status = "Error"
        finally:
            if placement is not None:
                obj.Placement = placement

    def onChanged(self, obj: Any, prop: str) -> None:  # noqa: N802 - FreeCAD callback
        if prop in PARAMETER_NAMES and hasattr(obj, "touch"):
            obj.touch()

    def dumps(self) -> dict[str, int]:
        """FreeCAD serialization hook; all state lives in document properties."""

        return {"version": 1}

    def loads(self, state: Any) -> None:
        del state


def create_nameplate(document: Any | None = None) -> Any:
    """Create and recompute an Arabic nameplate in *document*.

    When no document is supplied, the active document is used or a new one is
    created. The returned FeaturePython object is ready for property editing.
    """

    import FreeCAD as App  # type: ignore

    doc = document or App.ActiveDocument
    if doc is None:
        doc = App.newDocument("ArabicNameplate")
    obj = doc.addObject("Part::FeaturePython", "ArabicNameplate")
    obj.Label = "Arabic Nameplate"
    ArabicNameplateProxy(obj)
    if getattr(App, "GuiUp", False):
        from .view_provider import ViewProviderArabicNameplate

        ViewProviderArabicNameplate(obj.ViewObject)
    if hasattr(doc, "recompute"):
        doc.recompute()
    return obj
