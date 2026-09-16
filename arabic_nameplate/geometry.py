"""FreeCAD solid generation for parametric, correctly-shaped text."""

from __future__ import annotations

from collections import defaultdict
import math
from typing import Iterable

import FreeCAD as App  # type: ignore
import Part  # type: ignore

from .parameters import DEFAULTS, parameters_from_object, validate_parameters
from .qt_compat import QtCore, QtGui
from .shaping import available_font_families, shape_text


def _point(element) -> tuple[float, float]:
    # Flip Qt's downward Y axis into the conventional CAD XY plane.
    return float(element.x), -float(element.y)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _path_wires(path, tolerance: float):
    """Convert a QPainterPath to closed Part wires, preserving cubic curves."""
    contours: list[list[tuple]] = []
    current: list[tuple] = []
    start = None
    cursor = None
    index = 0
    count = path.elementCount()
    while index < count:
        element = path.elementAt(index)
        kind = int(getattr(element.type, "value", element.type))
        if kind == 0:  # MoveToElement
            if current:
                contours.append(current)
            current = []
            start = _point(element)
            cursor = start
            index += 1
        elif kind == 1:  # LineToElement
            target = _point(element)
            if cursor is not None and _distance(cursor, target) > tolerance * 1.0e-4:
                current.append(("line", cursor, target))
            cursor = target
            index += 1
        elif kind == 2 and index + 2 < count:  # CurveToElement + 2 data points
            control1 = _point(element)
            control2 = _point(path.elementAt(index + 1))
            target = _point(path.elementAt(index + 2))
            if cursor is not None:
                current.append(("cubic", cursor, control1, control2, target))
            cursor = target
            index += 3
        else:
            index += 1
    if current:
        contours.append(current)

    wires = []
    for segments in contours:
        if not segments:
            continue
        first = segments[0][1]
        last = segments[-1][-1]
        if _distance(last, first) > tolerance * 1.0e-4:
            segments.append(("line", last, first))
        edges = []
        for segment in segments:
            if segment[0] == "line":
                a, b = segment[1], segment[2]
                if _distance(a, b) > tolerance * 1.0e-4:
                    edges.append(Part.makeLine(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0)))
            else:
                points = [App.Vector(p[0], p[1], 0) for p in segment[1:]]
                curve = Part.BezierCurve()
                curve.setPoles(points)
                edges.append(curve.toShape())
        if not edges:
            continue
        try:
            wire = Part.Wire(edges)
            if wire.isClosed():
                wires.append(wire)
        except Exception as exc:
            raise ValueError(f"A font contour could not be converted to a closed CAD wire: {exc}") from exc
    return wires


def _faces_from_path(path, tolerance: float):
    """Create filled faces with counters via FreeCAD's nested-wire face maker."""
    wires = _path_wires(path, tolerance)
    if not wires:
        return []
    try:
        made = Part.makeFace(wires, "Part::FaceMakerBullseye")
    except Exception as exc:
        raise ValueError(f"Closed font contours could not be resolved into filled CAD faces: {exc}") from exc
    faces = [face for face in made.Faces if face.Area > tolerance * tolerance * 1.0e-6]
    if not faces:
        raise ValueError("Closed font contours produced no non-degenerate CAD faces.")
    return faces


def _compound(shapes: Iterable):
    items = [shape for shape in shapes if shape is not None and not shape.isNull()]
    if not items:
        return Part.Shape()
    if len(items) == 1:
        return items[0]
    return Part.makeCompound(items)


def _fuse(shapes: Iterable):
    items = [shape for shape in shapes if shape is not None and not shape.isNull()]
    if not items:
        return Part.Shape()
    result = items[0]
    try:
        for shape in items[1:]:
            result = result.fuse(shape)
    except Exception as exc:
        raise ValueError(f"OpenCASCADE could not fuse overlapping nameplate geometry: {exc}") from exc
    try:
        return result.removeSplitter()
    except Exception:
        return result


def _extrude_faces(faces, z: float, height: float):
    solids = []
    vector = App.Vector(0, 0, height)
    for face in faces:
        placed = face.copy()
        placed.translate(App.Vector(0, 0, z))
        solids.append(placed.extrude(vector))
    return _compound(solids)


def _stroker(width: float, join: str, tolerance: float):
    stroker = QtGui.QPainterPathStroker()
    stroker.setWidth(width * 2.0)
    joins = {
        "Round": QtCore.Qt.PenJoinStyle.RoundJoin,
        "Miter": QtCore.Qt.PenJoinStyle.MiterJoin,
        "Bevel": QtCore.Qt.PenJoinStyle.BevelJoin,
    }
    stroker.setJoinStyle(joins[join])
    stroker.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    stroker.setMiterLimit(4.0)
    if hasattr(stroker, "setCurveThreshold"):
        stroker.setCurveThreshold(max(0.001, min(1.0, tolerance / max(width, tolerance))))
    return stroker


def _scaled_outline_paths(glyphs, width: float, join: str, tolerance: float):
    """Do planar outline booleans in Qt at a scale bounded by tolerance.

    Qt's path boolean engine operates in device-like coordinates. Enlarging
    before its curve flattening, then shrinking the result, bounds that
    flattening to roughly CurveTolerance and avoids very costly OCC unions of
    every self-overlapping stroke segment.
    """
    scale = max(1.0, 2.0 / tolerance)
    up = QtGui.QTransform()
    up.scale(scale, scale)
    down = QtGui.QTransform()
    down.scale(1.0 / scale, 1.0 / scale)
    combined = QtGui.QPainterPath()
    for glyph in glyphs:
        candidate = up.map(glyph.path)
        combined.addPath(candidate)
    stroke = _stroker(width * scale, join, tolerance * scale)
    text_fill = combined.simplified()
    stroke_fill = stroke.createStroke(combined).simplified()
    expanded = text_fill.united(stroke_fill).simplified()
    band = expanded.subtracted(text_fill).simplified()
    return down.map(text_fill), down.map(expanded), down.map(band)


def _flatten_scaled_path(source, tolerance: float):
    """Flatten at an explicit CAD-space tolerance and return scaled polygons."""
    scale = 1.0 / tolerance
    transform = QtGui.QTransform()
    transform.scale(scale, scale)
    result = QtGui.QPainterPath()
    result.setFillRule(QtCore.Qt.FillRule.WindingFill)
    for polygon in source.toSubpathPolygons(transform):
        result.addPolygon(polygon)
    return result.simplified()


def _united_scaled_glyphs(glyphs, tolerance: float):
    result = QtGui.QPainterPath()
    result.setFillRule(QtCore.Qt.FillRule.WindingFill)
    first = True
    for glyph in glyphs:
        flat = _flatten_scaled_path(glyph.path, tolerance)
        result = flat if first else result.united(flat)
        first = False
    return result.simplified()


def _faces_from_scaled_path(path, tolerance: float):
    scale = 1.0 / tolerance
    wires = []
    for polygon in path.toSubpathPolygons():
        points = [App.Vector(float(point.x()) / scale, -float(point.y()) / scale, 0.0)
                  for point in polygon]
        if len(points) < 3:
            continue
        if points[0].distanceToPoint(points[-1]) > tolerance * 1.0e-5:
            points.append(points[0])
        try:
            wires.append(Part.makePolygon(points))
        except Exception as exc:
            raise ValueError(f"A flattened text contour could not become a CAD wire: {exc}") from exc
    if not wires:
        return []
    try:
        made = Part.makeFace(wires, "Part::FaceMakerBullseye")
    except Exception as exc:
        raise ValueError(f"Flattened text contours could not become printable faces: {exc}") from exc
    if not made.isValid():
        raise ValueError("The selected text and offset settings produced an invalid planar face.")
    # Boolean recombination can leave sub-micron seam slivers at coincident
    # polygon vertices. They are far below the requested approximation scale
    # and cause false extra solids in otherwise connected output.
    minimum_area = tolerance * tolerance * 0.01
    return [face for face in made.Faces if face.Area >= minimum_area]


def _outline_scaled_paths(text_path, width: float, join: str, tolerance: float):
    scale = 1.0 / tolerance
    stroke = _stroker(width * scale, join, 1.0)
    stroke_path = stroke.createStroke(text_path).simplified()
    expanded = text_path.united(stroke_path).simplified()
    band = expanded.subtracted(text_path).simplified()
    return expanded, band


def _scaled_path_from_faces(faces, tolerance: float):
    scale = 1.0 / tolerance
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.FillRule.WindingFill)
    for face in faces:
        for wire in face.Wires:
            polygon = QtGui.QPolygonF()
            for vertex in wire.OrderedVertexes:
                polygon.append(QtCore.QPointF(vertex.X * scale, -vertex.Y * scale))
            if polygon:
                polygon.append(polygon[0])
                path.addPolygon(polygon)
    return path.simplified()


def _layered_shape(entries, tolerance: float):
    """Union footprints per Z interval before extrusion for fast valid solids."""
    entries = [(path, float(z0), float(z1)) for path, z0, z1 in entries
               if path is not None and z1 > z0]
    levels = sorted({z for _path, z0, z1 in entries for z in (z0, z1)})
    layers = []
    for low, high in zip(levels, levels[1:]):
        middle = (low + high) * 0.5
        active = [path for path, z0, z1 in entries if z0 < middle < z1]
        if not active:
            continue
        planar = active[0]
        for path in active[1:]:
            planar = planar.united(path)
        faces = _faces_from_scaled_path(planar.simplified(), tolerance)
        layers.append(_extrude_faces(faces, low, high - low))
    return _fuse(layers)


def _glyph_faces(shaped, tolerance: float):
    components = []
    all_faces = []
    for glyph in shaped.glyphs:
        faces = _faces_from_path(glyph.path, tolerance)
        for face in faces:
            components.append((face, glyph.word_id, glyph.line_index, glyph.baseline_y))
            all_faces.append(face)
    return all_faces, components


def _nearest_points(a, b):
    try:
        distance, pairs, _ = a.distToShape(b)
        if pairs:
            p1, p2 = pairs[0]
            return float(distance), (p1.x, p1.y), (p2.x, p2.y)
    except Exception:
        pass
    ca, cb = a.CenterOfMass, b.CenterOfMass
    p1, p2 = (ca.x, ca.y), (cb.x, cb.y)
    return _distance(p1, p2), p1, p2


def _bridge_face(p1, p2, width: float, tolerance: float):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length <= tolerance * 1.0e-4:
        return None
    ux, uy = dx / length, dy / length
    px, py = -uy * width * 0.5, ux * width * 0.5
    # Positive overlap avoids bridges that merely touch the target solids.
    overlap = max(width * 0.35, tolerance * 2.0)
    a = (p1[0] - ux * overlap, p1[1] - uy * overlap)
    b = (p2[0] + ux * overlap, p2[1] + uy * overlap)
    points = [
        App.Vector(a[0] + px, a[1] + py, 0),
        App.Vector(b[0] + px, b[1] + py, 0),
        App.Vector(b[0] - px, b[1] - py, 0),
        App.Vector(a[0] - px, a[1] - py, 0),
    ]
    return Part.Face(Part.makePolygon(points + [points[0]]))


def _mst_bridge_faces(components, width: float, tolerance: float):
    if len(components) < 2:
        return []
    connected = {0}
    remaining = set(range(1, len(components)))
    bridges = []
    while remaining:
        best = None
        for i in connected:
            for j in remaining:
                distance, p1, p2 = _nearest_points(components[i], components[j])
                if best is None or distance < best[0]:
                    best = (distance, i, j, p1, p2)
        if best is None:
            break
        _, _, target, p1, p2 = best
        face = _bridge_face(p1, p2, width, tolerance)
        if face is not None:
            bridges.append(face)
        connected.add(target)
        remaining.remove(target)
    return bridges


def _baseline_faces(components, baseline_y: float, width: float, offset: float, tolerance: float):
    if not components:
        return []
    xmin = min(face.BoundBox.XMin for face in components)
    xmax = max(face.BoundBox.XMax for face in components)
    # Positive offset moves the rail below the typographic baseline in CAD Y.
    bar_y = baseline_y - offset
    pad = width * 0.5
    bar = Part.makePlane(max(xmax - xmin + 2 * pad, width), width,
                         App.Vector(xmin - pad, bar_y - width * 0.5, 0))
    faces = [bar]
    for component in components:
        _distance_value, on_bar, on_component = _nearest_points(bar, component)
        stem = _bridge_face(on_bar, on_component, width, tolerance)
        if stem is not None:
            faces.append(stem)
    return faces


def _connection_groups(components, scope: str):
    groups = defaultdict(list)
    if scope == "All":
        groups[0] = list(components)
    else:
        for face, word_id, line_index, _baseline in components:
            # Missing source indexes stay isolated by glyph/line rather than
            # accidentally joining two user-visible words.
            key = (line_index, word_id if word_id is not None else id(face))
            groups[key].append((face, word_id, line_index, _baseline))
    result = []
    for records in groups.values():
        faces = [record[0] for record in records]
        baseline = min(record[3] for record in records)
        result.append((faces, baseline))
    return result


def _rounded_rectangle_path(bounds, margin: float, radius: float):
    x = bounds.XMin - margin
    y = -bounds.YMax - margin  # convert CAD bounds back to Qt coordinates
    width = bounds.XLength + 2.0 * margin
    height = bounds.YLength + 2.0 * margin
    radius = min(max(radius, 0.0), width * 0.5, height * 0.5)
    path = QtGui.QPainterPath()
    path.addRoundedRect(QtCore.QRectF(x, y, width, height), radius, radius)
    return path


def _solid_count(shape) -> int:
    try:
        return len(shape.Solids)
    except Exception:
        return 0


def _offset_faces(faces, distance: float):
    if distance <= 0:
        return _fuse(faces)
    offsets = []
    for face in faces:
        try:
            offset = face.makeOffset2D(distance, 0, False, False, False)
        except Exception as exc:
            raise ValueError(f"Could not create the requested contour base margin: {exc}") from exc
        offsets.extend(offset.Faces)
    return _fuse(offsets)


def build_nameplate(params: dict) -> dict:
    """Build parametric nameplate solids and return the documented result map."""
    values = dict(DEFAULTS)
    values.update(parameters_from_object(params))
    errors = validate_parameters(values)
    if errors:
        raise ValueError(" ".join(errors))

    tolerance = float(values["CurveTolerance"])
    shaped = shape_text(values)
    warnings = list(shaped.warnings)
    text_path = _united_scaled_glyphs(shaped.glyphs, tolerance)
    text_faces = _faces_from_scaled_path(text_path, tolerance)
    if not text_faces:
        raise ValueError("The shaped text could not be converted into closed printable faces.")

    # Retain word and line provenance after shaping while resolving each
    # group's overlaps in the same tolerance-controlled planar representation.
    glyph_groups = defaultdict(list)
    for index, glyph in enumerate(shaped.glyphs):
        key = (glyph.line_index, glyph.word_id if glyph.word_id is not None else ("glyph", index))
        glyph_groups[key].append(glyph)
    components = []
    for (_line, _word), glyphs in glyph_groups.items():
        group_path = _united_scaled_glyphs(glyphs, tolerance)
        group_faces = _faces_from_scaled_path(group_path, tolerance)
        for face in group_faces:
            components.append((face, glyphs[0].word_id, glyphs[0].line_index,
                               min(g.baseline_y for g in glyphs)))

    footprint = _compound(text_faces)
    if footprint.isNull():
        raise ValueError("The shaped text produced an empty CAD footprint.")

    outline_footprint = None
    outline_band = None
    outline_expanded_path = text_path
    outline_width = float(values["OutlineWidth"])
    if outline_width > 0:
        outline_expanded_path, outline_band_path = _outline_scaled_paths(
            text_path, outline_width, str(values["OutlineJoin"]), tolerance)
        outline_band = _compound(_faces_from_scaled_path(outline_band_path, tolerance))
        outline_footprint = _compound([footprint, outline_band])

    connection_mode = str(values["ConnectionMode"])
    bridge_faces = []
    if connection_mode != "None":
        groups = _connection_groups(components, str(values["ConnectionScope"]))
        for group, baseline_y in groups:
            if connection_mode == "Bridges":
                bridge_faces.extend(_mst_bridge_faces(group, float(values["BridgeWidth"]), tolerance))
            else:
                bridge_faces.extend(_baseline_faces(group, baseline_y, float(values["BridgeWidth"]),
                                                    float(values["BaselineOffset"]), tolerance))

    support_path = outline_expanded_path
    if bridge_faces:
        support_path = support_path.united(_scaled_path_from_faces(bridge_faces, tolerance)).simplified()
    support_faces = _faces_from_scaled_path(support_path, tolerance)
    support_footprint = _compound(support_faces)

    base_style = str(values["BaseStyle"])
    base_height = float(values["BaseHeight"]) if base_style != "None" else 0.0
    z_top = base_height
    base_shape = None
    base_scaled_path = None
    if base_style == "Rounded rectangle":
        base_qt_path = _rounded_rectangle_path(support_footprint.BoundBox, float(values["BaseMargin"]),
                                               float(values["CornerRadius"]))
        base_scaled_path = _flatten_scaled_path(base_qt_path, tolerance)
        base_shape = _extrude_faces(_faces_from_scaled_path(base_scaled_path, tolerance), 0.0, base_height)
    elif base_style == "Contour":
        margin = float(values["BaseMargin"])
        if margin > 0:
            scale = 1.0 / tolerance
            margin_stroke = _stroker(margin * scale, "Round", 1.0)
            base_path = support_path.united(margin_stroke.createStroke(support_path)).simplified()
        else:
            base_path = support_path
        base_scaled_path = base_path
        base_shape = _extrude_faces(_faces_from_scaled_path(base_path, tolerance), 0.0, base_height)

    text_shape = _extrude_faces(footprint.Faces, z_top, float(values["TextHeight"]))
    outline_shape = None
    if outline_band is not None and outline_band.Faces:
        outline_shape = _extrude_faces(outline_band.Faces, z_top, float(values["OutlineHeight"]))
    connection_shape = None
    bridge_path = None
    if bridge_faces:
        bridge_path = _scaled_path_from_faces(bridge_faces, tolerance)
        bridge_footprint = _compound(_faces_from_scaled_path(bridge_path, tolerance))
        connection_shape = _extrude_faces(bridge_footprint.Faces, z_top, float(values["BridgeHeight"]))

    layer_entries = []
    if base_scaled_path is not None:
        layer_entries.append((base_scaled_path, 0.0, base_height))
    layer_entries.append((text_path, z_top, z_top + float(values["TextHeight"])))
    if outline_width > 0:
        layer_entries.append((outline_band_path, z_top, z_top + float(values["OutlineHeight"])))
    if bridge_path is not None:
        layer_entries.append((bridge_path, z_top, z_top + float(values["BridgeHeight"])))
    shape = _layered_shape(layer_entries, tolerance)
    if shape.isNull() or not shape.Solids:
        raise ValueError("FreeCAD could not create valid solids from the selected settings.")
    try:
        if not shape.isValid():
            raise ValueError("OpenCASCADE reports invalid output; try a larger Curve tolerance or wider features.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"FreeCAD could not validate the generated shape: {exc}") from exc

    count = _solid_count(shape)
    if count > 1:
        warnings.append(f"Generated {count} separate printable solids.")
    minimum = float(values["MinFeature"])
    if minimum > 0:
        narrow = sum(1 for face, *_ in components
                     if min(face.BoundBox.XLength, face.BoundBox.YLength) < minimum)
        if narrow:
            warnings.append(f"{narrow} text feature(s) are smaller than the {minimum:g} mm minimum-feature target.")
        if outline_width and outline_width < minimum:
            warnings.append("Outline width is below the minimum-feature target.")
        if connection_mode != "None" and float(values["BridgeWidth"]) < minimum:
            warnings.append("Bridge width is below the minimum-feature target.")

    result = {
        "shape": shape,
        "warnings": warnings,
        "font_families": list(shaped.families),
        "solid_count": count,
        "text_shape": text_shape,
    }
    if outline_shape is not None:
        result["outline_shape"] = outline_shape
    if base_shape is not None:
        result["base_shape"] = base_shape
    return result


__all__ = ["available_font_families", "build_nameplate"]
