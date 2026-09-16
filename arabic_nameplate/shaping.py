"""Unicode shaping and bidi layout backed by Qt's native text engine.

QTextLayout performs script shaping, bidi reordering, ligatures, and font
fallback. QRawFont is only used after layout, to retrieve the exact outline of
each glyph selected by the shaper.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from .qt_compat import QtCore, QtGui, ensure_gui_application, glyph_runs


@dataclass
class ShapedGlyph:
    path: object
    word_id: Optional[int]
    line_index: int
    baseline_y: float
    family: str


@dataclass
class ShapedText:
    glyphs: list[ShapedGlyph]
    path: object
    families: list[str]
    requested_family: str
    resolved_family: str
    warnings: list[str]


def available_font_families() -> list[str]:
    ensure_gui_application()
    return sorted(str(x) for x in QtGui.QFontDatabase.families())


def _direction(value: str):
    qt = QtCore.Qt
    if value == "RTL":
        return getattr(qt, "RightToLeft", qt.LayoutDirection.RightToLeft)
    if value == "LTR":
        return getattr(qt, "LeftToRight", qt.LayoutDirection.LeftToRight)
    return getattr(qt, "LayoutDirectionAuto", qt.LayoutDirection.LayoutDirectionAuto)


def _word_map(text: str, first_id: int) -> tuple[dict[int, int], int]:
    result: dict[int, int] = {}
    next_id = first_id
    for match in re.finditer(r"\S+", text, flags=re.UNICODE):
        # QTextLayout indexes UTF-16 code units, while Python indexes Unicode
        # scalar values. Convert explicitly so astral characters do not shift
        # every following word assignment.
        utf16_start = len(text[:match.start()].encode("utf-16-le")) // 2
        utf16_end = len(text[:match.end()].encode("utf-16-le")) // 2
        for index in range(utf16_start, utf16_end):
            result[index] = next_id
        next_id += 1
    return result, next_id


def _run_indexes(run, count: int) -> list[int]:
    try:
        values = list(run.stringIndexes())
    except (AttributeError, TypeError):
        values = []
    if len(values) == count:
        return [int(x) for x in values]
    return [-1] * count


def _style_path(path, raw_font, font_size: float, bold: bool, italic: bool):
    # QRawFont normally resolves a real bold/italic face. Some Arabic families
    # lack one, so explicitly synthesize the missing style instead of silently
    # returning unchanged geometry.
    if italic:
        style = raw_font.style()
        normal_style = getattr(QtGui.QFont, "StyleNormal", None)
        if normal_style is None:
            normal_style = QtGui.QFont.Style.StyleNormal
        if style == normal_style:
            transform = QtGui.QTransform()
            transform.shear(-0.20, 0.0)
            path = transform.map(path)
    if bold:
        try:
            weight = int(raw_font.weight())
        except (TypeError, ValueError):
            weight = 400
        bold_weight = getattr(QtGui.QFont, "Bold", None)
        if bold_weight is None:
            bold_weight = int(QtGui.QFont.Weight.Bold)
        if weight < int(bold_weight):
            stroker = QtGui.QPainterPathStroker()
            stroker.setWidth(max(font_size * 0.055, 0.01))
            stroker.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
            path = path.united(stroker.createStroke(path))
    return path


def shape_text(params: dict) -> ShapedText:
    ensure_gui_application()
    text = str(params["Text"])
    if not text or not text.strip():
        raise ValueError("Text must contain at least one visible character.")

    family = str(params["FontFamily"]).strip()
    font_size = float(params["FontSize"])
    font = QtGui.QFont(family) if family else QtGui.QFont()
    font.setPixelSize(max(1, int(round(font_size * 64.0))))
    # Work in 1/64 units and scale down. This avoids integer pixel-size
    # quantization while keeping FontSize equal to the typographic em in mm.
    font.setBold(bool(params["Bold"]))
    font.setItalic(bool(params["Italic"]))
    font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    info = QtGui.QFontInfo(font)
    resolved = str(info.family())
    warnings: list[str] = []
    if family and resolved.casefold() != family.casefold():
        warnings.append(f"Requested font '{family}' resolved to '{resolved}'.")

    lines = text.split("\n")
    line_records = []
    max_width = 0.0
    word_id = 0
    for line_index, line_text in enumerate(lines):
        word_indexes, word_id = _word_map(line_text, word_id)
        layout_text = line_text if line_text else " "
        layout = QtGui.QTextLayout(layout_text, font)
        option = QtGui.QTextOption()
        option.setTextDirection(_direction(str(params["Direction"])))
        layout.setTextOption(option)
        layout.beginLayout()
        qline = layout.createLine()
        qline.setLineWidth(1.0e9)
        qline.setPosition(QtCore.QPointF(0.0, 0.0))
        layout.endLayout()
        width = float(qline.naturalTextWidth()) / 64.0 if line_text else 0.0
        max_width = max(max_width, width)
        line_records.append((line_index, line_text, layout, qline, width, word_indexes))

    combined = QtGui.QPainterPath()
    glyphs: list[ShapedGlyph] = []
    families: list[str] = []
    line_advance = font_size * float(params["LineSpacing"])
    alignment = str(params["Alignment"])
    missing_glyphs = 0
    for line_index, line_text, layout, qline, width, word_indexes in line_records:
        if not line_text:
            continue
        if alignment == "Center":
            align_x = (max_width - width) * 0.5
        elif alignment == "Right":
            align_x = max_width - width
        else:
            align_x = 0.0
        baseline_y = line_index * line_advance
        for run in glyph_runs(layout, qline.textStart(), qline.textLength()):
            raw = run.rawFont()
            run_family = str(raw.familyName())
            if run_family and run_family not in families:
                families.append(run_family)
            indexes = list(run.glyphIndexes())
            positions = list(run.positions())
            source_indexes = _run_indexes(run, len(indexes))
            for glyph_index, position, source_index in zip(indexes, positions, source_indexes):
                if int(glyph_index) == 0:
                    missing_glyphs += 1
                path = raw.pathForGlyph(int(glyph_index))
                path = _style_path(path, raw, font_size * 64.0,
                                   bool(params["Bold"]), bool(params["Italic"]))
                transform = QtGui.QTransform()
                transform.scale(1.0 / 64.0, 1.0 / 64.0)
                path = transform.map(path)
                path.translate(float(position.x()) / 64.0 + align_x,
                               float(position.y()) / 64.0 + baseline_y)
                # addPath preserves the font's exact cubic outlines. CAD
                # booleans merge overlapping glyph solids later.
                combined.addPath(path)
                word = word_indexes.get(source_index) if source_index >= 0 else None
                cad_baseline_y = -(float(position.y()) / 64.0 + baseline_y)
                glyphs.append(ShapedGlyph(path, word, line_index, cad_baseline_y, run_family))

    if combined.isEmpty():
        raise ValueError("The selected font produced no printable glyph outlines.")
    if not families:
        families.append(resolved)
    if missing_glyphs:
        warnings.append(f"The selected and fallback fonts contain {missing_glyphs} missing-glyph placeholder(s).")
    if any(g.word_id is None for g in glyphs) and str(params["ConnectionScope"]) == "Words":
        warnings.append("The Qt binding did not expose all glyph source indexes; some connectors may be grouped conservatively.")
    if any(name.casefold() != resolved.casefold() for name in families):
        warnings.append("Qt used fallback fonts for characters missing from the selected family: " + ", ".join(families))
    return ShapedText(glyphs, combined, families, family, resolved, warnings)
