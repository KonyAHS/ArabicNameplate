"""Offscreen integration smoke for the real FreeCAD/PySide task panel.

Run through tools/run_freecad_tests.sh, not a stock Python installation.
"""

import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import FreeCAD as App
import FreeCADGui as Gui
import Part


def fake_build(params):
    """Keep UI/transaction checks fast; geometry has its own integration test."""
    shape = Part.makeBox(float(params["FontSize"]), 8.0, float(params["TextHeight"]))
    return {"shape": shape, "warnings": [], "font_families": [params["FontFamily"]]}


geometry = types.ModuleType("arabic_nameplate.geometry")
geometry.build_nameplate = fake_build
sys.modules["arabic_nameplate.geometry"] = geometry

from arabic_nameplate.feature import create_nameplate
from arabic_nameplate.panel import LTR, PLAIN_TEXT, RTL, NameplateTaskPanel, QtWidgets
from arabic_nameplate.commands import active_panel, enter_edit
from arabic_nameplate.view_provider import ViewProviderArabicNameplate


def main():
    print("UI smoke: creating offscreen Qt application", flush=True)
    Gui.setupWithoutGUI()
    application = QtWidgets.QApplication.instance()
    if application is None:
        application = QtWidgets.QApplication(["ArabicNameplateUiTest"])
    document = App.newDocument("ArabicNameplateUiTest")
    document.UndoMode = 1
    obj = create_nameplate(document)
    obj.Text = "سلام FreeCAD"
    document.recompute()

    original_size = obj.FontSize.Value
    class RestoredView:
        Object = obj
        ShapeColor = (0.80, 0.20, 0.10)

    restored_view = RestoredView()
    restored_provider = ViewProviderArabicNameplate()
    restored_provider.attach(restored_view)
    assert restored_view.ShapeColor == (0.80, 0.20, 0.10)
    panel = NameplateTaskPanel(obj)
    assert panel.form.objectName() == "ArabicNameplateTaskPanel"
    assert panel.getStandardButtons()
    assert panel._widgets["FontFamily"].count() > 0
    assert panel.preview.textFormat() == PLAIN_TEXT

    panel._set_widget_value("Text", "سلام")
    panel._set_widget_value("Direction", "RTL")
    panel._update_preview()
    assert panel.preview.layoutDirection() == RTL
    panel._set_widget_value("Direction", "LTR")
    panel._update_preview()
    assert panel.preview.layoutDirection() == LTR

    panel._set_widget_value("FontSize", original_size + 3.0)
    panel._dirty = True
    assert panel.update_model()
    assert abs(obj.FontSize.Value - original_size - 3.0) < 1e-7
    panel.reject()
    assert abs(obj.FontSize.Value - original_size) < 1e-7

    panel = NameplateTaskPanel(obj)
    panel._set_widget_value("Text", "مرحباً بالعالم")
    panel._set_widget_value("FontSize", original_size + 2.0)
    panel._dirty = True
    panel._update_preview()
    updated = panel.update_model()
    if not updated:
        raise AssertionError("UI update failed: " + str(obj.LastError))
    assert abs(obj.FontSize.Value - original_size - 2.0) < 1e-7

    panel.form.resize(440, 780)
    panel.form.show()
    application.processEvents()
    screenshot = "/tmp/arabic-nameplate-panel.png"
    assert panel.form.grab().save(screenshot)
    panel.tabs.setCurrentIndex(1)
    application.processEvents()
    assert panel.form.grab().save("/tmp/arabic-nameplate-panel-outline.png")
    panel.accept()
    document.undo()
    assert abs(obj.FontSize.Value - original_size) < 1e-7

    print("UI smoke: checking validation and create cancellation", flush=True)
    panel = NameplateTaskPanel(obj)
    panel._set_widget_value("Text", "")
    panel._dirty = True
    assert panel.accept() is False
    assert panel._transaction_open
    panel.reject()

    document.openTransaction("Create Arabic nameplate")
    temporary = create_nameplate(document)
    temporary_name = temporary.Name
    panel = NameplateTaskPanel(temporary, transaction_open=True, is_new=True)
    panel.reject()
    assert document.getObject(temporary_name) is None

    if hasattr(Gui, "ActiveDocument") or hasattr(Gui, "activeDocument"):
        print("UI smoke: checking native FreeCAD edit mode", flush=True)
        assert enter_edit(obj)
        edit_panel = active_panel(obj)
        assert edit_panel is not None
        gui_document = getattr(Gui, "ActiveDocument", None) or Gui.activeDocument()
        assert gui_document.getInEdit() is not None
        edit_panel.reject()
        assert gui_document.getInEdit() is None
    else:
        print("UI smoke: edit mode unavailable under setupWithoutGUI; skipped", flush=True)

    assert os.path.isfile(screenshot) and os.path.getsize(screenshot) > 0
    App.closeDocument(document.Name)
    print("UI smoke passed; screenshot:", screenshot)


if __name__ == "__main__":
    main()
