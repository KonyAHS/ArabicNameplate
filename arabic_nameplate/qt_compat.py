"""Small PySide compatibility layer used by the geometry engine."""

from __future__ import annotations

try:  # FreeCAD 1.0/1.1 builds normally provide PySide6.
    from PySide6 import QtCore, QtGui
except ImportError:  # pragma: no cover - retained for older FreeCAD releases.
    from PySide2 import QtCore, QtGui  # type: ignore


_owned_application = None


def ensure_gui_application():
    """Return a GUI application, creating a minimal one for FreeCADCmd/tests."""
    global _owned_application
    app = QtGui.QGuiApplication.instance()
    if app is None:
        _owned_application = QtGui.QGuiApplication(["ArabicNameplate"])
        app = _owned_application
    return app


def enum_value(owner, scoped_name: str, legacy_name: str):
    """Get an enum member under both Qt 6 and Qt 5 Python bindings."""
    scoped = getattr(owner, scoped_name, None)
    if scoped is not None:
        return scoped
    return getattr(owner, legacy_name)


def glyph_runs(layout, start: int, length: int):
    """Request source indexes where supported, for word-aware connectors."""
    flags_type = getattr(QtGui.QTextLayout, "GlyphRunRetrievalFlag", None)
    if flags_type is not None:
        return layout.glyphRuns(start, length, flags_type.RetrieveAll)
    return layout.glyphRuns(start, length)

