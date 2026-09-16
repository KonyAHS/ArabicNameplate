"""End-to-end build, persistence and export checks using the real geometry."""

import os
import tempfile

import FreeCAD as App
import Import
import Mesh
import Part

from arabic_nameplate.feature import create_nameplate


doc = App.newDocument("RealGeometryIntegration")
obj = create_nameplate(doc)
obj.Text = "لوحة اسم"
obj.Direction = "RTL"
obj.ConnectionMode = "Bridges"
obj.ConnectionScope = "All"
obj.Placement.Base = App.Vector(2.0, 3.0, 4.0)
doc.recompute()
assert not obj.LastError, obj.LastError
assert not obj.Shape.isNull()
assert obj.Shape.isValid()
assert obj.Shape.Solids
assert obj.SolidCount == len(obj.Shape.Solids)
initial_depth = obj.OverallDepth.Value

with tempfile.TemporaryDirectory() as temp_dir:
    document_path = os.path.join(temp_dir, "arabic-nameplate.FCStd")
    stl_path = os.path.join(temp_dir, "arabic-nameplate.stl")
    step_path = os.path.join(temp_dir, "arabic-nameplate.step")
    doc.saveAs(document_path)
    App.closeDocument(doc.Name)

    restored = App.openDocument(document_path)
    restored_obj = restored.getObject("ArabicNameplate")
    assert restored_obj.Text == "لوحة اسم"
    assert restored_obj.Placement.Base == App.Vector(2.0, 3.0, 4.0)
    restored_obj.TextHeight = restored_obj.TextHeight.Value + 1.5
    restored.recompute()
    assert not restored_obj.LastError, restored_obj.LastError
    assert restored_obj.OverallDepth.Value > initial_depth
    assert restored_obj.Placement.Base == App.Vector(2.0, 3.0, 4.0)

    Mesh.export([restored_obj], stl_path)
    Import.export([restored_obj], step_path)
    assert os.path.getsize(stl_path) > 100
    assert os.path.getsize(step_path) > 100
    exported_mesh = Mesh.Mesh(stl_path)
    assert exported_mesh.CountFacets > 0
    assert exported_mesh.isSolid()
    exported_step = Part.Shape()
    exported_step.read(step_path)
    assert not exported_step.isNull()
    assert exported_step.Solids
    App.closeDocument(restored.Name)

print("Real Arabic nameplate persistence and export checks passed")
