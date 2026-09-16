"""Render the real sample FCStd tessellation to an angled PNG preview."""

import os

import FreeCAD as App

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sample_path = os.path.join(project_dir, "examples", "sample-nameplate.FCStd")
preview_path = os.path.join(project_dir, "examples", "sample-nameplate.png")

doc = App.openDocument(sample_path)
obj = doc.getObject("ArabicNameplate")
if obj is None or obj.Shape.isNull():
    raise RuntimeError("The sample document has no ArabicNameplate geometry.")
vertices, facets = obj.Shape.tessellate(0.10)
if not vertices or not facets:
    raise RuntimeError("FreeCAD produced no display mesh for the sample.")

xyz = [(point.x, point.y, point.z) for point in vertices]
triangles = [[xyz[index] for index in facet] for facet in facets]
z_min = min(point[2] for point in xyz)
z_max = max(point[2] for point in xyz)
span = max(z_max - z_min, 1.0e-9)
colors = []
for triangle in triangles:
    level = (sum(point[2] for point in triangle) / 3.0 - z_min) / span
    colors.append((0.10 + 0.16 * level, 0.38 + 0.26 * level, 0.40 + 0.25 * level, 1.0))

figure = pyplot.figure(figsize=(12, 7), dpi=160, facecolor="#f6f4ef")
axis = figure.add_subplot(111, projection="3d", facecolor="#f6f4ef")
mesh = Poly3DCollection(triangles, facecolors=colors, edgecolor=(0.06, 0.20, 0.21, 0.24), linewidth=0.18)
axis.add_collection3d(mesh)
x_values = [point[0] for point in xyz]
y_values = [point[1] for point in xyz]
z_values = [point[2] for point in xyz]
axis.set_xlim(min(x_values), max(x_values))
axis.set_ylim(min(y_values), max(y_values))
axis.set_zlim(min(z_values), max(z_values))
axis.set_box_aspect((max(x_values) - min(x_values), max(y_values) - min(y_values), span))
axis.view_init(elev=35, azim=-65)
axis.set_axis_off()
figure.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.99)
figure.savefig(preview_path, bbox_inches="tight", pad_inches=0.08, facecolor=figure.get_facecolor())
pyplot.close(figure)
App.closeDocument(doc.Name)
print("Created " + preview_path)
