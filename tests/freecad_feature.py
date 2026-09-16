"""Headless integration checks run by tools/run_freecad_tests.sh."""

import os
import sys
import tempfile
import types

import FreeCAD as App
import Part


def fake_build(params):
    if params["Text"] == "NO_SOLID":
        return {"shape": Part.Face(Part.makePlane(2.0, 2.0))}
    shape = Part.makeBox(float(params["FontSize"]), 8.0, float(params["TextHeight"]))
    return {"shape": shape, "warnings": ["integration warning"], "font_families": [params["FontFamily"]]}


geometry = types.ModuleType("arabic_nameplate.geometry")
geometry.build_nameplate = fake_build
sys.modules["arabic_nameplate.geometry"] = geometry

from arabic_nameplate.feature import create_nameplate


doc = App.newDocument("FeatureIntegration")
doc.UndoMode = 1
obj = create_nameplate(doc)
obj.Text = "اختبار الحفظ"
obj.FontSize = 27.0
obj.TextHeight = 4.5
obj.Bold = True
obj.BaselineOffset = -3.0
obj.Placement.Base = App.Vector(11.0, 12.0, 13.0)
doc.recompute()
assert obj.Status == "Generated with warnings", obj.Status
assert obj.SolidCount == 1
assert abs(obj.OverallWidth.Value - 27.0) < 1e-7
assert obj.Placement.Base == App.Vector(11.0, 12.0, 13.0)

doc.openTransaction("Edit Arabic nameplate")
obj.Text = "تراجع"
doc.commitTransaction()
doc.undo()
assert obj.Text == "اختبار الحفظ"

with tempfile.TemporaryDirectory() as temp_dir:
    file_name = os.path.join(temp_dir, "feature.FCStd")
    doc.recompute()
    doc.saveAs(file_name)
    App.closeDocument(doc.Name)
    restored = App.openDocument(file_name)
    restored_obj = restored.getObject("ArabicNameplate")
    assert restored_obj.Text == "اختبار الحفظ"
    assert abs(restored_obj.FontSize.Value - 27.0) < 1e-7
    assert abs(restored_obj.TextHeight.Value - 4.5) < 1e-7
    assert restored_obj.Bold is True
    assert abs(restored_obj.BaselineOffset.Value - -3.0) < 1e-7
    assert restored_obj.Placement.Base == App.Vector(11.0, 12.0, 13.0)
    restored_obj.TextHeight = 6.0
    restored.recompute()
    assert restored_obj.SolidCount == 1
    assert abs(restored_obj.OverallDepth.Value - 6.0) < 1e-7

    restored_obj.FontSize = 0.0
    restored.recompute()
    assert restored_obj.Status == "Error"
    assert "Font size" in restored_obj.LastError
    assert restored_obj.Shape.isNull()
    assert restored_obj.SolidCount == 0
    assert restored_obj.Placement.Base == App.Vector(11.0, 12.0, 13.0)

    restored_obj.FontSize = 27.0
    restored_obj.Text = "NO_SOLID"
    restored.recompute()
    assert restored_obj.Status == "Error"
    assert "no solids" in restored_obj.LastError
    assert restored_obj.Shape.isNull()
    App.closeDocument(restored.Name)

print("FreeCAD FeaturePython integration checks passed")
