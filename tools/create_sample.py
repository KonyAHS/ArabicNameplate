"""Generate the editable sample FCStd using the installed FreeCAD runtime."""

import os

import FreeCAD as App

try:
    import FreeCADGui as Gui

    Gui.showMainWindow()
except ImportError:
    Gui = None

from arabic_nameplate.feature import create_nameplate


project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sample_dir = os.path.join(project_dir, "examples")
os.makedirs(sample_dir, exist_ok=True)
sample_path = os.path.join(sample_dir, "sample-nameplate.FCStd")

doc = App.newDocument("ArabicNameplateSample")
obj = create_nameplate(doc)
obj.Label = "Arabic Nameplate — مرحباً"
obj.Text = "مرحباً"
obj.Direction = "RTL"
obj.Alignment = "Center"
obj.ConnectionMode = "Bridges"
obj.ConnectionScope = "All"
doc.recompute()
if obj.LastError:
    raise RuntimeError(obj.LastError)
if obj.Shape.isNull() or not obj.Shape.isValid() or obj.SolidCount != 1:
    raise RuntimeError("Sample generation did not produce one valid connected solid.")
doc.recompute()
doc.saveAs(sample_path)
App.closeDocument(doc.Name)
print("Created " + sample_path)
