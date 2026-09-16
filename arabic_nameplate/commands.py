"""GUI commands registered by the Arabic Nameplate workbench."""

from __future__ import annotations

import os


ICON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "icons"))
_ACTIVE_PANEL = None


def _icon(name):
    return os.path.join(ICON_DIR, name + ".svg")


def _active_document():
    import FreeCAD as App
    import FreeCADGui as Gui

    document = App.ActiveDocument
    if document is None:
        document = App.newDocument("ArabicNameplate")
    if _gui_active_document() is None and hasattr(Gui, "activeDocument"):
        Gui.activeDocument()
    return document


def _gui_active_document():
    import FreeCADGui as Gui

    document = getattr(Gui, "ActiveDocument", None)
    if document is None and hasattr(Gui, "activeDocument"):
        document = Gui.activeDocument()
    return document


def _dialog_is_open():
    try:
        import FreeCADGui as Gui
        return bool(Gui.Control.activeDialog())
    except Exception:
        return False


def is_nameplate(obj):
    return bool(obj and getattr(getattr(obj, "Proxy", None), "Type", "") == "ArabicNameplate")


def selected_nameplate():
    import FreeCADGui as Gui

    for obj in Gui.Selection.getSelection():
        if is_nameplate(obj):
            return obj
    return None


def open_editor(obj, is_new=False, transaction_open=False):
    global _ACTIVE_PANEL
    import FreeCADGui as Gui
    from .panel import NameplateTaskPanel

    if _dialog_is_open():
        return False
    panel = NameplateTaskPanel(
        obj, transaction_open=transaction_open, is_new=is_new
    )
    _ACTIVE_PANEL = panel
    try:
        Gui.Control.showDialog(panel)
    except Exception:
        _ACTIVE_PANEL = None
        panel.reject()
        raise
    return True


def enter_edit(obj):
    """Enter FreeCAD edit mode so context-menu and toolbar editing agree."""
    import FreeCAD as App
    import FreeCADGui as Gui

    if _dialog_is_open():
        return False
    if App.ActiveDocument is not obj.Document:
        App.setActiveDocument(obj.Document.Name)
    gui_document = _gui_active_document()
    return bool(gui_document and gui_document.setEdit(obj.Name))


def active_panel(obj=None):
    if _ACTIVE_PANEL is None:
        return None
    if obj is not None and _ACTIVE_PANEL.obj is not obj:
        return None
    return _ACTIVE_PANEL


def clear_active_panel(panel):
    global _ACTIVE_PANEL
    if _ACTIVE_PANEL is panel:
        _ACTIVE_PANEL = None


class CreateCommand:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {
            "Pixmap": _icon("create-nameplate"),
            "MenuText": "New Arabic Nameplate",
            "ToolTip": "Create an editable Arabic or multilingual 3D nameplate",
            "Accel": "N, A",
        }

    def IsActive(self):  # noqa: N802
        return not _dialog_is_open()

    def Activated(self):  # noqa: N802
        from .feature import create_nameplate

        if _dialog_is_open():
            return
        document = _active_document()
        document.openTransaction("Create Arabic nameplate")
        try:
            obj = create_nameplate(document)
            document.recompute()
            if not str(getattr(obj, "LastError", "")).strip():
                try:
                    view = _gui_active_document().activeView()
                    view.viewAxonometric()
                    view.fitAll()
                except Exception:
                    pass
            if not open_editor(obj, is_new=True, transaction_open=True):
                document.abortTransaction()
        except Exception:
            document.abortTransaction()
            raise


class EditCommand:
    def GetResources(self):  # noqa: N802
        return {
            "Pixmap": _icon("edit-nameplate"),
            "MenuText": "Edit Arabic Nameplate",
            "ToolTip": "Edit all text, shape, connection, and printing parameters",
        }

    def IsActive(self):  # noqa: N802
        return not _dialog_is_open() and selected_nameplate() is not None

    def Activated(self):  # noqa: N802
        obj = selected_nameplate()
        if obj:
            enter_edit(obj)


class ExportCommand:
    def __init__(self, file_type):
        self.file_type = file_type

    def GetResources(self):  # noqa: N802
        upper = self.file_type.upper()
        return {
            "Pixmap": _icon("export-" + self.file_type),
            "MenuText": "Export Nameplate as " + upper,
            "ToolTip": "Validate and export the selected nameplate as " + upper,
        }

    def IsActive(self):  # noqa: N802
        return not _dialog_is_open() and selected_nameplate() is not None

    def Activated(self):  # noqa: N802
        import FreeCADGui as Gui

        obj = selected_nameplate()
        if obj is None:
            return
        obj.Document.recompute()
        error = _shape_error(obj)
        if error:
            _message("Cannot export", error, critical=True)
            return
        try:
            from PySide import QtWidgets  # type: ignore
        except ImportError:
            try:
                from PySide6 import QtWidgets  # type: ignore
            except ImportError:
                from PySide2 import QtWidgets  # type: ignore
        extension = "." + self.file_type
        filter_text = "%s files (*%s)" % (self.file_type.upper(), extension)
        suggested = _safe_filename(getattr(obj, "Label", "ArabicNameplate")) + extension
        result = QtWidgets.QFileDialog.getSaveFileName(
            Gui.getMainWindow(), "Export Arabic Nameplate", suggested, filter_text
        )
        filename = result[0] if isinstance(result, tuple) else result
        if not filename:
            return
        if not filename.lower().endswith(extension):
            filename += extension
        try:
            if self.file_type == "stl":
                import Mesh
                Mesh.export([obj], filename)
            else:
                import Import
                Import.export([obj], filename)
        except Exception as exc:
            _message("Export failed", str(exc), critical=True)


def _shape_error(obj):
    last_error = str(getattr(obj, "LastError", "")).strip()
    if last_error:
        return "The current parameters did not build successfully:\n" + last_error
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        return "The selected nameplate has no exportable shape. Choose Update 3D first."
    if not shape.isValid():
        return "The selected nameplate shape is invalid. Adjust the parameters and update it."
    if not shape.Solids:
        return "The selected nameplate contains no solid bodies to export."
    return ""


def _safe_filename(value):
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(value))
    return cleaned.strip("_") or "ArabicNameplate"


def _message(title, text, critical=False):
    try:
        from PySide import QtWidgets  # type: ignore
    except ImportError:
        try:
            from PySide6 import QtWidgets  # type: ignore
        except ImportError:
            from PySide2 import QtWidgets  # type: ignore
    icon = QtWidgets.QMessageBox.Critical if critical else QtWidgets.QMessageBox.Information
    box = QtWidgets.QMessageBox(icon, title, text)
    box.exec()


COMMANDS = {
    "ArabicNameplate_Create": CreateCommand(),
    "ArabicNameplate_Edit": EditCommand(),
    "ArabicNameplate_ExportSTL": ExportCommand("stl"),
    "ArabicNameplate_ExportSTEP": ExportCommand("step"),
}


def register_commands():
    import FreeCADGui as Gui

    for name, command in COMMANDS.items():
        Gui.addCommand(name, command)
