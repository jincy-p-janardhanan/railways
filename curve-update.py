import csv
import ast
import math
import numpy as np
from scipy.optimize import least_squares
import re

def fit_circle_radius(points):
    """Fit circle to all points using least squares and return radius."""
    points = np.array(points)
    x = points[:, 0]
    y = points[:, 1]
    
    def calc_radius(params, x, y):
        h, k, r = params
        return np.sqrt((x - h)**2 + (y - k)**2) - r

    x_m, y_m = np.mean(x), np.mean(y)
    r_m = np.mean(np.sqrt((x - x_m)**2 + (y - y_m)**2))
    initial_guess = [x_m, y_m, r_m]

    result = least_squares(calc_radius, initial_guess, args=(x, y))
    h, k, r = result.x

    if r <= 0:
        return float('inf')
    return r

def calculate_arc_length(coords):
    """Calculate total arc length given a list of (x,y) points"""
    length = 0
    for i in range(len(coords)-1):
        length += math.dist(coords[i], coords[i+1])
    return length

def parse_qgspointxy_list(s):
    points = re.findall(r'POINT\(([-\d\.]+) ([-\d\.]+)\)', s)
    return [(float(x), float(y)) for x, y in points]

def update_curve_csv(input_csv, output_csv=None):
    if output_csv is None:
        output_csv = input_csv

    with open(input_csv, 'r', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with open(output_csv, 'w', newline='') as f:
        fieldnames = reader.fieldnames
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            coords = parse_qgspointxy_list(row["Coordinates"])
            arc_length = calculate_arc_length(coords)
            R = fit_circle_radius(coords)
            curvature = 1/R if R != float('inf') else 0
            angle_deg = (arc_length / R) * (180 / math.pi) if R != float('inf') else 0

            row["Arc Length (m)"] = f"{arc_length:.6f}"
            row["Radius (m)"] = f"{R:.6f}"
            row["Curvature (1/m)"] = f"{curvature:.8f}"
            row["Angle (deg)"] = f"{angle_deg:.6f}"

            writer.writerow(row)

    print(f"Updated CSV saved to {output_csv}")

update_curve_csv('curve.csv', 'curve-updated.csv')

