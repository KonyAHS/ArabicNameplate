import os
import runpy
import sys
import tempfile
import types
import unittest


class InstallerTests(unittest.TestCase):
    def test_installs_only_runtime_files_and_refuses_overwrite(self):
        messages = []
        with tempfile.TemporaryDirectory() as user_dir:
            freecad = types.ModuleType("FreeCAD")
            freecad.getUserAppDataDir = lambda: user_dir + os.sep
            freecad.Console = types.SimpleNamespace(
                PrintError=lambda message: messages.append(("error", message)),
                PrintMessage=lambda message: messages.append(("info", message)),
            )
            widgets = types.SimpleNamespace(
                QMessageBox=types.SimpleNamespace(
                    warning=lambda *_args: None,
                    information=lambda *_args: None,
                ),
                QFileDialog=types.SimpleNamespace(getExistingDirectory=lambda *_args: ""),
            )
            pyside = types.ModuleType("PySide6")
            pyside.QtWidgets = widgets
            old_freecad = sys.modules.get("FreeCAD")
            old_pyside = sys.modules.get("PySide6")
            sys.modules["FreeCAD"] = freecad
            sys.modules["PySide6"] = pyside
            try:
                macro = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "InstallArabicNameplate.FCMacro"))
                runpy.run_path(macro)
                target = os.path.join(user_dir, "Mod", "ArabicNameplate")
                self.assertTrue(os.path.isfile(os.path.join(target, "package.xml")))
                self.assertTrue(os.path.isfile(os.path.join(target, "arabic_nameplate", "feature.py")))
                self.assertTrue(os.path.isfile(os.path.join(target, "resources", "icons", "workbench.svg")))
                self.assertFalse(os.path.exists(os.path.join(target, "tests")))
                runpy.run_path(macro)
                self.assertTrue(any("already installed" in message for _kind, message in messages))
            finally:
                if old_freecad is None:
                    sys.modules.pop("FreeCAD", None)
                else:
                    sys.modules["FreeCAD"] = old_freecad
                if old_pyside is None:
                    sys.modules.pop("PySide6", None)
                else:
                    sys.modules["PySide6"] = old_pyside


if __name__ == "__main__":
    unittest.main()
