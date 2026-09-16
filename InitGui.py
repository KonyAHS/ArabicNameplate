"""FreeCAD GUI entry point for the Arabic Nameplate workbench."""

import FreeCADGui as Gui


class ArabicNameplateWorkbench(Gui.Workbench):
    import os as _os
    import arabic_nameplate as _package

    MenuText = "Arabic Nameplate"
    ToolTip = "Parametric Arabic and multilingual 3D nameplates"
    Icon = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(_package.__file__))),
        "resources", "icons", "workbench.svg",
    )

    def Initialize(self):  # noqa: N802 - FreeCAD API
        from arabic_nameplate.commands import register_commands

        register_commands()
        self.commands = [
            "ArabicNameplate_Create",
            "ArabicNameplate_Edit",
            "Separator",
            "ArabicNameplate_ExportSTL",
            "ArabicNameplate_ExportSTEP",
        ]
        self.appendToolbar("Arabic Nameplate", self.commands)
        self.appendMenu("Arabic Nameplate", self.commands)

    def Activated(self):  # noqa: N802
        pass

    def Deactivated(self):  # noqa: N802
        pass

    def GetClassName(self):  # noqa: N802
        return "Gui::PythonWorkbench"


Gui.addWorkbench(ArabicNameplateWorkbench())
