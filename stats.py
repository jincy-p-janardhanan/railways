import json
from math import radians, sin, cos, sqrt, atan2

# --- Haversine function ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

# --- Load GeoJSON ---
with open("mumbai_railways_updated_with_elevations.geojson") as f:
    geojson = json.load(f)

group1_coords = []  # For "line added"
group2_coords = []  

for feature in geojson["features"]:
    coords = feature["geometry"]["coordinates"]
    name = feature["properties"].get("name", "")
    
    if name.strip().lower() == "line added":
        group1_coords.append(coords)
    else:
        group2_coords.append(coords)

def total_distance(coord_groups):
    total = 0
    for coords in coord_groups:
        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i][0], coords[i][1]
            lon2, lat2 = coords[i+1][0], coords[i+1][1]
            total += haversine(lat1, lon1, lat2, lon2)
    return total

# Calculate distances
dist_group1 = total_distance(group1_coords)
dist_group2 = total_distance(group2_coords)

print(f"Total distance of all railway lines obtained from OSM: {dist_group2:.3f} m")
print(f"Total distance of all railway lines hand-drawn: {dist_group1:.3f} m")

