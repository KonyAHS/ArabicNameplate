"""Native Qt task panel for creating and editing Arabic nameplates."""

from __future__ import annotations

try:  # FreeCAD exposes the matching Qt binding through PySide.
    from PySide import QtCore, QtGui  # type: ignore
    try:
        from PySide import QtWidgets  # type: ignore
    except ImportError:  # FreeCAD 0.20/PySide2 compatibility
        QtWidgets = QtGui
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore

from .parameters import DEFAULTS, PARAMETERS, parameters_from_object, validate_parameters


def _enum(namespace, old_name, group_name):
    """Return a Qt enum in both the Qt5 and scoped Qt6 APIs."""
    value = getattr(namespace, old_name, None)
    if value is not None:
        return value
    return getattr(getattr(namespace, group_name), old_name)


ALIGN_CENTER = _enum(QtCore.Qt, "AlignCenter", "AlignmentFlag")
ALIGN_LEFT = _enum(QtCore.Qt, "AlignLeft", "AlignmentFlag")
ALIGN_RIGHT = _enum(QtCore.Qt, "AlignRight", "AlignmentFlag")
RTL = _enum(QtCore.Qt, "RightToLeft", "LayoutDirection")
LTR = _enum(QtCore.Qt, "LeftToRight", "LayoutDirection")
HORIZONTAL = _enum(QtCore.Qt, "Horizontal", "Orientation")
PLAIN_TEXT = _enum(QtCore.Qt, "PlainText", "TextFormat")


class DimensionDiagram(QtWidgets.QWidget):
    """Small side-view explanation of the three printable height levels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = dict(DEFAULTS)
        self.setMinimumHeight(112)
        self.setToolTip(
            "Side view: Base Height starts at the build plate, Outline Height "
            "is the lower border, and Text Height is the raised face."
        )

    def setValues(self, values):
        self._values.update(values)
        self.update()

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = self.rect().adjusted(10, 8, -10, -8)
        base_enabled = self._values.get("BaseStyle", "None") != "None"
        base_h = max(0.0, float(self._values.get("BaseHeight", 0.0))) if base_enabled else 0.0
        outline_h = max(0.0, float(self._values.get("OutlineHeight", 0.0)))
        text_h = max(0.0, float(self._values.get("TextHeight", 0.0)))
        maximum = max(base_h + outline_h, base_h + text_h, 0.1)
        floor = rect.bottom() - 18
        usable = max(30, rect.height() - 32)

        def y_for(value):
            return floor - int(usable * value / maximum)

        painter.setPen(QtGui.QPen(QtGui.QColor("#59636e"), 1))
        painter.drawLine(rect.left(), floor, rect.right(), floor)
        center = rect.center().x()
        base_top = y_for(base_h)
        if base_enabled:
            painter.fillRect(rect.left() + 4, base_top, rect.width() - 8,
                             max(1, floor - base_top), QtGui.QColor("#9ca3af"))
        outline_width = max(80, int(rect.width() * 0.62))
        outline_top = y_for(base_h + outline_h)
        text_width = max(38, int(rect.width() * 0.30))
        outline_enabled = float(self._values.get("OutlineWidth", 0.0)) > 0
        if outline_enabled:
            side_width = max(1, (outline_width - text_width) // 2)
            painter.fillRect(center - outline_width // 2, outline_top, side_width,
                             max(1, base_top - outline_top), QtGui.QColor("#3b82f6"))
            painter.fillRect(center + text_width // 2, outline_top, side_width,
                             max(1, base_top - outline_top), QtGui.QColor("#3b82f6"))
        text_top = y_for(base_h + text_h)
        painter.fillRect(center - text_width // 2, text_top, text_width,
                         max(1, base_top - text_top), QtGui.QColor("#0f766e"))
        painter.setPen(QtGui.QColor("#20262e"))
        base_label = "Base %.2f" % base_h if base_enabled else "Base off"
        outline_label = "Outline %.2f" % outline_h if outline_enabled else "Outline off"
        painter.drawText(rect.left() + 4, floor + 14,
                         "%s  ·  %s  ·  Text %.2f mm" %
                         (base_label, outline_label, text_h))
        painter.end()


class NameplateTaskPanel:
    """FreeCAD task panel with a fast 2D preview and explicit 3D update."""

    PRESETS = {
        "Raised lettering": {
            "TextHeight": 3.0,
            "OutlineWidth": 1.2,
            "OutlineHeight": 1.2,
        },
        "Pronounced rim": {
            "TextHeight": 1.2,
            "OutlineWidth": 1.8,
            "OutlineHeight": 3.0,
        },
        "Nearly flat": {
            "TextHeight": 1.0,
            "OutlineWidth": 0.8,
            "OutlineHeight": 0.8,
        },
    }

    def __init__(self, obj, transaction_open=False, is_new=False):
        self.obj = obj
        self.document = obj.Document
        self.is_new = is_new
        self._transaction_open = transaction_open
        self._dirty = False
        self._finishing = False
        self._widgets = {}
        if not transaction_open:
            self.document.openTransaction("Edit Arabic nameplate")
            self._transaction_open = True

        self.form = QtWidgets.QWidget()
        self.form.setObjectName("ArabicNameplateTaskPanel")
        self.form.setWindowTitle("Arabic Nameplate")
        self._build_ui()
        self._load(parameters_from_object(self.obj))
        self._update_preview()
        self._update_object_status()

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self.form)
        outer.setContentsMargins(8, 8, 8, 8)

        heading = QtWidgets.QLabel("Arabic Nameplate")
        font = heading.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        heading.setFont(font)
        outer.addWidget(heading)

        intro = QtWidgets.QLabel(
            "Edit dimensions in millimetres. The font preview updates immediately; "
            "choose Update 3D when you are ready to rebuild the solid."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(QtWidgets.QLabel("Preset"))
        self.preset = QtWidgets.QComboBox()
        self.preset.addItem("Custom")
        self.preset.addItems(list(self.PRESETS))
        self.preset.setToolTip("Presets change only the three raised-layer dimensions.")
        self.preset.currentTextChanged.connect(self._apply_preset)
        preset_row.addWidget(self.preset, 1)
        outer.addLayout(preset_row)

        self.tabs = QtWidgets.QTabWidget()
        outer.addWidget(self.tabs, 1)
        groups = ("Text", "Outline", "Base", "Connections", "Manufacturing")
        layouts = {}
        for group in groups:
            page = QtWidgets.QWidget()
            layout = QtWidgets.QFormLayout(page)
            layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            layouts[group] = layout
            self.tabs.addTab(page, group)

        for spec in PARAMETERS:
            widget = self._make_widget(spec)
            self._widgets[spec["name"]] = widget
            label = QtWidgets.QLabel(spec["label"])
            label.setToolTip(spec.get("help", ""))
            widget.setToolTip(spec.get("help", ""))
            layouts[spec["group"]].addRow(label, widget)

        text_page = self.tabs.widget(0)
        text_layout = text_page.layout()
        text_layout.addRow(QtWidgets.QLabel("Font preview (not to scale)"))
        self.preview = QtWidgets.QLabel()
        self.preview.setObjectName("ArabicNameplatePreview")
        self.preview.setMinimumHeight(92)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(PLAIN_TEXT)
        self.preview.setAlignment(ALIGN_CENTER)
        self.preview.setStyleSheet(
            "QLabel { background: palette(base); border: 1px solid palette(mid); "
            "border-radius: 4px; padding: 8px; }"
        )
        text_layout.addRow(self.preview)

        outline_page = self.tabs.widget(1)
        outline_layout = outline_page.layout()
        help_text = QtWidgets.QLabel(
            "Outline Width expands sideways around the glyphs. Outline Height "
            "and Text Height set independent thicknesses above the support surface."
        )
        help_text.setWordWrap(True)
        outline_layout.addRow(help_text)
        self.diagram = DimensionDiagram()
        outline_layout.addRow(self.diagram)

        hint = QtWidgets.QLabel(
            "Bridges join nearby components locally. Baseline adds a shared rail; "
            "scope can connect each word separately or the whole inscription."
        )
        hint.setWordWrap(True)
        layouts["Connections"].addRow(hint)

        self.status = QtWidgets.QLabel()
        self.status.setObjectName("ArabicNameplateStatus")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        self.update_button = QtWidgets.QPushButton("Update 3D")
        self.update_button.setObjectName("ArabicNameplateUpdate3D")
        self.update_button.setToolTip("Validate these settings and rebuild the FreeCAD solid.")
        self.update_button.clicked.connect(self.update_model)
        outer.addWidget(self.update_button)

    def _make_widget(self, spec):
        kind = spec["type"]
        if kind == "string":
            widget = QtWidgets.QPlainTextEdit()
            widget.setObjectName("Parameter_%s" % spec["name"])
            widget.setMaximumHeight(72)
            widget.textChanged.connect(self._parameter_changed)
            return widget
        if kind == "font":
            widget = QtWidgets.QFontComboBox()
            widget.setObjectName("Parameter_%s" % spec["name"])
            widget.currentFontChanged.connect(self._parameter_changed)
            return widget
        if kind == "bool":
            widget = QtWidgets.QCheckBox()
            widget.setObjectName("Parameter_%s" % spec["name"])
            widget.toggled.connect(self._parameter_changed)
            return widget
        if kind == "enum":
            widget = QtWidgets.QComboBox()
            widget.setObjectName("Parameter_%s" % spec["name"])
            widget.addItems(spec["choices"])
            widget.currentTextChanged.connect(self._parameter_changed)
            return widget
        widget = QtWidgets.QDoubleSpinBox()
        widget.setObjectName("Parameter_%s" % spec["name"])
        widget.setDecimals(3 if kind == "length" else 2)
        widget.setRange(float(spec.get("min", -1e9)), float(spec.get("max", 1e9)))
        widget.setSingleStep(float(spec.get("step", 0.1)))
        if kind == "length":
            widget.setSuffix(" mm")
        widget.valueChanged.connect(self._parameter_changed)
        return widget

    def _set_widget_value(self, name, value):
        widget = self._widgets[name]
        blocked = widget.blockSignals(True)
        try:
            if isinstance(widget, QtWidgets.QPlainTextEdit):
                widget.setPlainText(str(value))
            elif isinstance(widget, QtWidgets.QFontComboBox):
                widget.setCurrentFont(QtGui.QFont(str(value)))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QtWidgets.QComboBox):
                index = widget.findText(str(value))
                widget.setCurrentIndex(max(0, index))
            else:
                try:
                    value = value.Value
                except AttributeError:
                    pass
                widget.setValue(float(value))
        finally:
            widget.blockSignals(blocked)

    def _widget_value(self, name):
        widget = self._widgets[name]
        if isinstance(widget, QtWidgets.QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QtWidgets.QFontComboBox):
            return widget.currentFont().family()
        if isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()
        return widget.value()

    def _load(self, values):
        for spec in PARAMETERS:
            self._set_widget_value(spec["name"], values.get(spec["name"], spec["default"]))
        self._dirty = False

    def values(self):
        return {spec["name"]: self._widget_value(spec["name"]) for spec in PARAMETERS}

    def _parameter_changed(self, *_args):
        self._dirty = True
        blocked = self.preset.blockSignals(True)
        self.preset.setCurrentIndex(0)
        self.preset.blockSignals(blocked)
        self._update_preview()
        self._show_pending_status()

    def _apply_preset(self, name):
        values = self.PRESETS.get(name)
        if not values:
            return
        for key, value in values.items():
            self._set_widget_value(key, value)
        self._dirty = True
        self._update_preview()
        self._show_pending_status()

    def _update_preview(self):
        values = self.values()
        font = QtGui.QFont(str(values["FontFamily"]))
        font.setBold(bool(values["Bold"]))
        font.setItalic(bool(values["Italic"]))
        font.setPointSizeF(max(11.0, min(64.0, float(values["FontSize"]) * 2.0)))
        self.preview.setFont(font)
        self.preview.setText(values["Text"] or " ")
        direction = values["Direction"]
        if direction == "Auto":
            direction = _text_direction(values["Text"])
        self.preview.setLayoutDirection(RTL if direction == "RTL" else LTR)
        alignment = {"Left": ALIGN_LEFT, "Right": ALIGN_RIGHT}.get(
            values["Alignment"], ALIGN_CENTER
        )
        self.preview.setAlignment(alignment | _enum(QtCore.Qt, "AlignVCenter", "AlignmentFlag"))
        self.diagram.setValues(values)
        self._sync_relevance(values)

    def _sync_relevance(self, values):
        """Disable inputs that cannot affect the current geometry."""
        base_style = values["BaseStyle"]
        base_enabled = base_style != "None"
        for name in ("BaseMargin", "BaseHeight"):
            self._widgets[name].setEnabled(base_enabled)
        self._widgets["CornerRadius"].setEnabled(base_style == "Rounded rectangle")

        connection_mode = values["ConnectionMode"]
        connected = connection_mode != "None"
        for name in ("ConnectionScope", "BridgeWidth", "BridgeHeight"):
            self._widgets[name].setEnabled(connected)
        self._widgets["BaselineOffset"].setEnabled(connection_mode == "Baseline")

    def _show_pending_status(self):
        errors = validate_parameters(self.values())
        if errors:
            self.status.setStyleSheet("color: #b42318;")
            self.status.setText("Fix before updating: " + " • ".join(errors))
        else:
            self.status.setStyleSheet("color: #8a5b00;")
            self.status.setText("Settings changed — choose Update 3D to rebuild the solid.")

    def _assign_values(self, values):
        for spec in PARAMETERS:
            setattr(self.obj, spec["name"], values[spec["name"]])

    def update_model(self):
        values = self.values()
        errors = validate_parameters(values)
        if errors:
            self.status.setStyleSheet("color: #b42318;")
            self.status.setText("Cannot update: " + " • ".join(errors))
            return False
        self.update_button.setEnabled(False)
        self.status.setStyleSheet("")
        self.status.setText("Building 3D geometry…")
        try:
            self._assign_values(values)
            self.document.recompute()
        except Exception as exc:
            self.status.setStyleSheet("color: #b42318;")
            self.status.setText("Build failed: %s" % exc)
            return False
        finally:
            self.update_button.setEnabled(True)
        self._update_object_status()
        success = not bool(self._current_shape_error())
        if not success and not str(getattr(self.obj, "LastError", "")).strip():
            self.status.setStyleSheet("color: #b42318;")
            self.status.setText("Build failed: " + self._current_shape_error())
        if success and self.is_new:
            try:
                from .commands import _gui_active_document

                view = _gui_active_document().activeView()
                view.viewAxonometric()
                view.fitAll()
            except Exception:
                pass
        self._dirty = not success
        return success

    def _update_object_status(self):
        error = str(getattr(self.obj, "LastError", "")).strip()
        warnings = list(getattr(self.obj, "Warnings", []) or [])
        if error:
            self.status.setStyleSheet("color: #b42318;")
            self.status.setText("Build failed: " + error)
            return
        solids = int(getattr(self.obj, "SolidCount", 0) or 0)
        width = _quantity_value(getattr(self.obj, "OverallWidth", 0.0))
        height = _quantity_value(getattr(self.obj, "OverallHeight", 0.0))
        depth = _quantity_value(getattr(self.obj, "OverallDepth", 0.0))
        solid_label = "1 connected solid" if solids == 1 else "%d separate solids" % solids
        message = "%s · %.1f × %.1f × %.1f mm" % (
            solid_label, width, height, depth
        )
        if warnings:
            message += "\n" + " • ".join(str(item) for item in warnings)
            self.status.setStyleSheet("color: #8a5b00;")
        else:
            self.status.setStyleSheet("color: #19703e;")
        self.status.setText(message)

    def accept(self):
        if self._dirty and not self.update_model():
            return False
        error = self._current_shape_error()
        if error:
            self.status.setStyleSheet("color: #b42318;")
            self.status.setText("Cannot accept: " + error)
            return False
        if self._transaction_open:
            self.document.commitTransaction()
            self._transaction_open = False
        self._finish_gui()
        return True

    def reject(self):
        if self._transaction_open:
            self.document.abortTransaction()
            self._transaction_open = False
        self._finish_gui()
        return True

    def getStandardButtons(self):  # noqa: N802 - FreeCAD API
        box = QtWidgets.QDialogButtonBox
        standard = getattr(box, "StandardButton", box)
        buttons = standard.Ok | standard.Cancel
        return int(getattr(buttons, "value", buttons))

    def _current_shape_error(self):
        error = str(getattr(self.obj, "LastError", "")).strip()
        if error:
            return error
        shape = getattr(self.obj, "Shape", None)
        if shape is None or shape.isNull():
            return "the current build produced no shape."
        if not shape.isValid():
            return "the current build produced invalid geometry. Adjust the settings and update again."
        if not getattr(shape, "Solids", []):
            return "the current build contains no printable solids."
        return ""

    def _finish_gui(self):
        self._finishing = True
        from .commands import _gui_active_document, clear_active_panel

        try:
            import FreeCADGui as Gui
            gui_document = _gui_active_document()
            if gui_document is not None and gui_document.getInEdit() is not None:
                gui_document.resetEdit()
        except Exception:
            pass
        try:
            Gui.Control.closeDialog()
        except Exception:
            pass
        clear_active_panel(self)


def _quantity_value(value):
    try:
        return float(value.Value)
    except AttributeError:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


def _text_direction(text):
    """Infer a useful preview direction from the first strong character."""
    import unicodedata

    for character in text:
        bidi = unicodedata.bidirectional(character)
        if bidi in ("R", "AL"):
            return "RTL"
        if bidi == "L":
            return "LTR"
    return "LTR"
