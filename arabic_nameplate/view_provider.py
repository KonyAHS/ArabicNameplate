"""View provider for editable Arabic nameplate feature objects."""


class ViewProviderArabicNameplate:
    def __init__(self, view_object=None):
        self.Object = None
        if view_object is not None:
            view_object.Proxy = self
            self.Object = view_object.Object
            self._set_appearance(view_object)

    def attach(self, view_object):
        self.Object = view_object.Object

    @staticmethod
    def _set_appearance(view_object):
        """Apply a calm, readable default while preserving user editability."""
        settings = {
            "ShapeColor": (0.20, 0.58, 0.55),
            "LineColor": (0.10, 0.24, 0.27),
            "DisplayMode": "Flat Lines",
            "Deviation": 0.12,
            "AngularDeflection": 20.0,
        }
        for name, value in settings.items():
            if hasattr(view_object, name):
                try:
                    setattr(view_object, name, value)
                except Exception:
                    pass

    def getIcon(self):  # noqa: N802 - FreeCAD API
        from .commands import _icon

        return _icon("create-nameplate")

    def doubleClicked(self, view_object):  # noqa: N802
        from .commands import enter_edit

        return enter_edit(view_object.Object)

    def setEdit(self, view_object, _mode=0):  # noqa: N802
        from .commands import open_editor

        return open_editor(view_object.Object)

    def unsetEdit(self, _view_object, _mode=0):  # noqa: N802
        from .commands import active_panel

        panel = active_panel(_view_object.Object)
        if panel is not None and not panel._finishing:
            panel.reject()
        return True

    def claimChildren(self):  # noqa: N802
        return []

    def dumps(self):
        return None

    def loads(self, _state):
        return None
