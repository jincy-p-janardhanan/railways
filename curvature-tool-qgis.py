from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import *
import math, csv, os

# =====================
# Global Variables
# =====================
drawn_layer = None
save_file = None
target_crs = QgsCoordinateReferenceSystem("EPSG:3857")  # meters-based CRS

iface.messageBar().pushMessage("Toolbar", "Custom curvature toolbar loaded", level=Qgis.Info)

# =====================
# Helper Functions
# =====================

def create_drawing_layer():
    """Create a temporary layer to draw arcs"""
    global drawn_layer
    drawn_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "Drawn_Arcs", "memory")
    pr = drawn_layer.dataProvider()
    pr.addAttributes([
        QgsField("arc_len_m", QVariant.Double),
        QgsField("radius_m", QVariant.Double),
        QgsField("curvature_1pm", QVariant.Double),
        QgsField("angle_deg", QVariant.Double)
    ])
    drawn_layer.updateFields()
    QgsProject.instance().addMapLayer(drawn_layer)
    iface.setActiveLayer(drawn_layer)

def fit_circle_radius(points):
    """Fit circle using first, middle, and last points"""
    p1, p2, p3 = points[0], points[len(points)//2], points[-1]
    A = math.dist(p2, p3)
    B = math.dist(p1, p3)
    C = math.dist(p1, p2)
    s = (A + B + C) / 2
    area = math.sqrt(max(s*(s-A)*(s-B)*(s-C), 0))
    return (A * B * C) / (4 * area) if area != 0 else float('inf')

def calculate_curvature():
    """Calculate curvature of the most recently drawn arc"""
    global save_file
    if drawn_layer is None or drawn_layer.featureCount() == 0:
        QMessageBox.warning(None, "No Arc", "Please draw an arc first!")
        return

    # Find the most recent feature by highest feature ID
    last_fid = max(f.id() for f in drawn_layer.getFeatures())
    feat = drawn_layer.getFeature(last_fid)

    # Transform geometry to meters CRS
    xform = QgsCoordinateTransform(drawn_layer.crs(), target_crs, QgsProject.instance())
    geom_m = feat.geometry()
    geom_m.transform(xform)
    coords = geom_m.asPolyline()

    if len(coords) < 3:
        QMessageBox.warning(None, "Too few points", "Draw at least 3 points for curvature calculation.")
        return

    # Arc length in meters
    arc_length = sum(math.dist(coords[i], coords[i+1]) for i in range(len(coords)-1))
    # Radius & Curvature
    R = fit_circle_radius(coords)
    curvature = 1/R if R != float('inf') else 0
    # Angle in degrees
    angle_deg = (arc_length / R) * (180 / math.pi) if R != float('inf') else 0

    # Update attributes
    drawn_layer.startEditing()
    feat['arc_len_m'] = arc_length
    feat['radius_m'] = R
    feat['curvature_1pm'] = curvature
    feat['angle_deg'] = angle_deg
    drawn_layer.updateFeature(feat)
    drawn_layer.commitChanges()

    # Save to CSV
    if save_file is None:
        save_file, _ = QFileDialog.getSaveFileName(None, "Select CSV Save Location", "", "CSV Files (*.csv)")
        if not save_file:
            return
        with open(save_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Arc Length (m)", "Radius (m)", "Curvature (1/m)", "Angle (deg)", "Coordinates"])

    with open(save_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([arc_length, R, curvature, angle_deg, coords])

    QMessageBox.information(None, "Curvature", 
        f"Arc length: {arc_length:.3f} m\n"
        f"Radius: {R:.3f} m\n"
        f"Curvature: {curvature:.5f} 1/m\n"
        f"Angle: {angle_deg:.3f}°\n"
        f"Saved to CSV.")

    # OPTIONAL: Uncomment this to auto-delete older arcs so only the last remains
    drawn_layer.startEditing()
    for f in drawn_layer.getFeatures():
        if f.id() != last_fid:
            drawn_layer.deleteFeature(f.id())
    drawn_layer.commitChanges()

def reset_layer():
    """Clear all drawn arcs"""
    if drawn_layer:
        drawn_layer.startEditing()
        drawn_layer.dataProvider().truncate()
        drawn_layer.commitChanges()
        QMessageBox.information(None, "Reset", "All drawn arcs cleared.")

# =====================
# Toolbar Setup
# =====================
toolbar = iface.addToolBar("Curvature Toolbar")

# Draw Arc Action (just activates the layer)
draw_action = QAction(QIcon(), "Draw Arc", iface.mainWindow())
draw_action.triggered.connect(lambda: iface.setActiveLayer(drawn_layer))
toolbar.addAction(draw_action)

# Find Curvature
curv_action = QAction(QIcon(), "Find Curvature", iface.mainWindow())
curv_action.triggered.connect(calculate_curvature)
toolbar.addAction(curv_action)

# Reset
reset_action = QAction(QIcon(), "Reset", iface.mainWindow())
reset_action.triggered.connect(reset_layer)
toolbar.addAction(reset_action)

# =====================
# Initialize
# =====================
create_drawing_layer()
