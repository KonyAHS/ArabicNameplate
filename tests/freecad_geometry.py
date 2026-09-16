"""Native FreeCAD/Qt integration checks for the geometry engine.

Run inside the FreeCAD Python environment (see README development commands).
This is intentionally a script so it works in FreeCADCmd and snap runtimes
without requiring pytest in FreeCAD's bundled Python environment.
"""

from __future__ import annotations

import time

import FreeCAD as App  # type: ignore

from arabic_nameplate.geometry import build_nameplate
from arabic_nameplate.parameters import DEFAULTS
from arabic_nameplate.shaping import shape_text


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


started = time.perf_counter()

# Real HarfBuzz/Qt shaping: joined lam-alef is a single ligature, while an
# intervening space prevents the ligature. Mixed bidi text must remain usable.
joined = shape_text(dict(DEFAULTS, Text="لا", ConnectionMode="None"))
separate = shape_text(dict(DEFAULTS, Text="ل ا", ConnectionMode="None"))
mixed = shape_text(dict(DEFAULTS, Text="ABC مرحبا 123", Direction="Auto", ConnectionMode="None"))
check(len(joined.glyphs) < len(separate.glyphs), "Arabic lam-alef was not shaped as a ligature")
check(not mixed.path.isEmpty() and len(mixed.glyphs) >= 10, "Mixed bidi shaping produced no usable glyph run")

print("shaping ok %.2fs" % (time.perf_counter() - started), flush=True)

# Default dotted Arabic must be connected by its bridges into one printable
# mass, including detached dots/diacritics.
default_result = build_nameplate(DEFAULTS)
check(default_result["shape"].isValid(), "Default geometry is invalid")
check(default_result["solid_count"] == 1, "Default Bridges/All did not connect every text island")
check(default_result["shape"].BoundBox.ZLength >= DEFAULTS["TextHeight"] - 1e-6,
      "Default text height was not preserved")
print("default geometry ok %.2fs" % (time.perf_counter() - started), flush=True)

# A tall outline must be an exterior rim: no outline material may fill the
# centre above the independently lower text top.
rim_params = dict(DEFAULTS, Text="O", FontFamily="DejaVu Sans", ConnectionMode="None",
                  OutlineWidth=1.0, TextHeight=1.0, OutlineHeight=3.0)
rim = build_nameplate(rim_params)
check(rim["shape"].isValid(), "Raised-rim geometry is invalid")
check(rim["shape"].BoundBox.ZMax >= 3.0 - 1e-6, "Raised outline did not reach its requested height")
check(rim["text_shape"].common(rim["outline_shape"]).Volume < 1e-6,
      "Outline band overlaps/fills the text centre")
centre = rim["text_shape"].BoundBox.Center
check(not rim["text_shape"].isInside(App.Vector(centre.x, centre.y, 0.5), 1e-5, True),
      "The counter in O was filled")
print("counter and raised rim ok %.2fs" % (time.perf_counter() - started), flush=True)

# Word scope must not bridge whitespace; All must join it.
words = dict(DEFAULTS, Text="باب بيت", OutlineWidth=0.0, ConnectionMode="Bridges")
by_word = build_nameplate(dict(words, ConnectionScope="Words"))
all_words = build_nameplate(dict(words, ConnectionScope="All"))
check(by_word["solid_count"] >= 2, "Words scope unexpectedly joined separate words")
check(all_words["solid_count"] == 1, "All scope did not join separate words")
print("connection scopes ok %.2fs" % (time.perf_counter() - started), flush=True)

print("freecad geometry integration passed in %.2fs" % (time.perf_counter() - started), flush=True)

