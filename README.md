# Arabic Nameplate for FreeCAD

Arabic Nameplate is a parametric FreeCAD workbench for printable Arabic and
multilingual signs. It uses Qt's text shaper, so Arabic joining, bidirectional
text, ligatures, mixed Arabic/Latin text, and system-font fallback happen before
the glyphs become FreeCAD geometry.

The default design has raised letters on a wider, lower outline. The heights are
fully editable, so the outline can also rise above the text to form a rim. Every
input is stored as a named property on the FreeCAD object and remains editable
after the file is saved and reopened. Optional bridges, a baseline rail, or a
backing plate can turn separate glyphs and words into one or more printable masses.

## Install

The simplest install is to open
[`InstallArabicNameplate.FCMacro`](InstallArabicNameplate.FCMacro) in FreeCAD,
run it once, and restart FreeCAD. The macro copies this workbench into the active
FreeCAD profile's `Mod` directory.

For a manual install:

1. In FreeCAD, open **View → Panels → Python console** and run:

   ```python
   App.getUserAppDataDir() + "Mod"
   ```

2. Create that `Mod` directory if needed and copy this whole repository into it
   as a directory named `ArabicNameplate`. `InitGui.py` must end up directly at
   `…/Mod/ArabicNameplate/InitGui.py`.
3. Restart FreeCAD and choose **Arabic Nameplate** from the workbench selector.

Using `App.getUserAppDataDir()` matters for sandboxed packages. In particular,
the FreeCAD Snap normally reports a path below `~/snap/freecad/common`; use the
reported path rather than a conventional `~/.local/share/FreeCAD` path.

The workbench currently targets FreeCAD 1.0 or newer with Qt/PySide 6. The UI has
compatibility paths for PySide2-based FreeCAD builds, but the primary tested
configuration is FreeCAD 1.1.1/PySide6.

## Create and edit a sign

Choose **New Arabic Nameplate** on the toolbar. Enter text, choose any system font,
and set bold, italic, direction, and alignment. The font preview is immediate and
intentionally lightweight; it is not a geometric preview and does not show the
outline, connectors, exact wrapping, or physical scale. Choose **Update 3D** to
build the solid. This explicit update keeps long inscriptions from rebuilding on
every keystroke.

The side-view diagram explains the Z layers. With a base enabled, the base starts
at the build plate and the outline, text, and connectors begin at its top. Text
Height and Outline Height are their independent extrusion thicknesses above that
surface. Outline Width expands the glyphs in XY.

Press **OK** to keep the current build, or **Cancel** to restore every property to
its value before the editor opened. Double-click an existing nameplate in the
tree, or select it and choose **Edit Arabic Nameplate**, to reopen the same panel.

Select a valid, up-to-date nameplate and use **Export Nameplate as STL** for a
slicer or **Export Nameplate as STEP** for solid CAD exchange. Export recomputes
and validates the feature first; it will not write a previous shape after a failed
build.

## Parameters

All dimensions are millimetres.

| Group | Parameter | Meaning |
| --- | --- | --- |
| Text | Text | Arabic, Latin, numbers, multiple lines, or mixed-direction Unicode text |
| Text | Font Family | A family from the system font picker; Qt may use fallback faces per glyph |
| Text | Font Size | Typographic em size used to form glyph outlines |
| Text | Bold / Italic | Select a matching face, or synthesize the style when the font lacks one |
| Text | Alignment | Left, center, or right alignment between multiple lines |
| Text | Direction | Automatic bidi direction, forced RTL, or forced LTR |
| Text | Line Spacing | Baseline spacing as a multiple of font size |
| Text | Text Height | Raised-face extrusion above the support surface |
| Outline | Outline Width | Horizontal expansion around the glyph; zero disables the outline |
| Outline | Outline Height | Outline extrusion above the support surface; it may be below or above the text |
| Outline | Outline Join | Round, miter, or bevel treatment for offset corners |
| Base | Base Style | No base, a text-following contour, or a rounded rectangle |
| Base | Base Margin | XY clearance around the inscription |
| Base | Base Height | Backing thickness from the build plate |
| Base | Corner Radius | Radius for the rounded rectangle style |
| Connections | Connection Method | None, local bridges, or a continuous baseline rail |
| Connections | Connection Scope | Join all text together or keep words separate |
| Connections | Bridge Width | Minimum connector width in the XY plane |
| Connections | Bridge Height | Connector extrusion above the support surface |
| Connections | Baseline Offset | Vertical position of the baseline rail in the text plane |
| Manufacturing | Minimum Feature | Warning threshold for narrow printable details; zero disables it |
| Manufacturing | Curve Tolerance | Outline approximation error; smaller is smoother and heavier to compute |

The supplied presets change only Text Height, Outline Width, and Outline Height.
They leave text, fonts, bases, connectors, and manufacturing settings alone.

## Connection and printing guidance

Arabic shaping joins strokes visually, but a word can still contain several
disconnected geometric components, including dots. **Bridges** add short links
between nearby components. **Baseline** creates a shared rail. **Words** scope is
useful when each word should remain a separate print; **All** aims for a single
connected inscription. Words can still touch through wide outlines, and any
shared backing joins everything it reaches. A rounded rectangular base normally
makes one backing solid, while a contour base can remain disconnected. The status
below the editor reports the actual number of solids, so check it before export.

Font outlines vary greatly. Very thin strokes, overlapping contours, extreme
italic shear, large miter offsets, and tiny internal counters can be difficult for
the geometry kernel or a printer. Minimum Feature only changes the warning
threshold; it does not thicken the result. Increase Font Size or connector width,
use a sturdier font, reduce Outline Width, or switch Outline Join when a build
reports a problem. The warning is a heuristic based on small component bounding
boxes and configured outline/connector widths; it does not measure the minimum
wall thickness at every point. Inspect the exported model in a slicer before
printing.

For a simple two-colour print, use an outline and connectors shorter than the
text, then schedule a filament change at their top surface. With the default
no-base preset, that surface is 1.2 mm above the build plate; with a base, add
Base Height to the change height.
Fonts are referenced by family name rather than embedded in the `.FCStd` file;
opening a document on another computer can therefore select a fallback and change
the shape. The object's Resolved Font Families output records what Qt actually
used for the last successful build.

## Macro and scripting

[examples/ArabicWelcome.FCMacro](examples/ArabicWelcome.FCMacro) creates a sample
with raised text, a lower outline, all-letter bridges, and a rounded backing. The
same API is available to Python scripts:

```python
from arabic_nameplate import create_nameplate

plate = create_nameplate()
plate.Text = "أهلاً وسهلاً"
plate.FontSize = 24
plate.Bold = True
plate.ConnectionMode = "Bridges"
plate.Document.recompute()
```

Inspect `plate.Status`, `plate.LastError`, `plate.Warnings`, and `plate.SolidCount`
after recomputing in automated workflows.

## Development and tests

The parameter tests run without FreeCAD:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

The repository also supplies `tools/run_freecad_tests.sh` for integration tests
inside the FreeCAD runtime:

```bash
./tools/run_freecad_tests.sh tests/freecad_feature.py
./tools/run_freecad_tests.sh tests/freecad_real_geometry.py
./tools/run_freecad_tests.sh tests/freecad_ui.py
./tools/run_freecad_gui_test.sh
```

`tests/freecad_ui.py` creates the real Qt task panel
offscreen, checks the system font control and transaction behavior, and writes a
screenshot to `/tmp/arabic-nameplate-panel.png`. Geometry tests require FreeCAD,
Part, Qt, and usable system fonts; they are not substitutes for opening a sample
in the FreeCAD GUI and checking the resulting mesh in a slicer.

The last command launches the full FreeCAD GUI with isolated temporary user and
configuration directories. It uses a stub solid to keep the workbench-discovery,
command, task-panel, and edit-mode lifecycle check under one minute. It clears the
test selection before quitting because the FreeCAD 1.1.1 Snap has a reproducible
`MeasureGui` crash during offscreen shutdown when any selected object remains;
the same crash occurs in a baseline document without this workbench. The runner
preserves timeouts, assertion failures, and unexpected FreeCAD exit codes, and
prints the path to its captured `/tmp` log.

## License

MIT; see [LICENSE](LICENSE).
