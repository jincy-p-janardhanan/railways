import json
import folium
import branca.colormap as cm
import numpy as np
import re
import csv

# -------------------------
# Load GeoJSON
# -------------------------
with open("mumbai_railways_updated_with_elevations.geojson", "r") as f:
    geojson_data = json.load(f)

nodes = {}
ways = []

node_counter = 1  # create IDs for each coordinate
for feature in geojson_data["features"]:
    coords = feature["geometry"]["coordinates"]

    way_nodes_ids = []
    for coord in coords:
        lon, lat, elevation = coord  # GeoJSON: [lon, lat, elevation]
        node_id = node_counter
        nodes[node_id] = {
            "lat": lat,
            "lon": lon,
            "elevation": elevation
        }
        way_nodes_ids.append(node_id)
        node_counter += 1

    ways.append({
        "id": feature["properties"].get("id", None),
        "nodes": way_nodes_ids
    })

# Compute min/max lat/lon for map centering
all_lats = [n["lat"] for n in nodes.values()]
all_lons = [n["lon"] for n in nodes.values()]
min_lat, max_lat = min(all_lats), max(all_lats)
min_lon, max_lon = min(all_lons), max(all_lons)

print(f"Extracted {len(nodes)} nodes and {len(ways)} ways")

# -------------------------
# Create Base Map
# -------------------------
center_lat = (min_lat + max_lat) / 2
center_lon = (min_lon + max_lon) / 2
m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

# -------------------------
# Elevation Heatmap
# -------------------------
elevations = [node['elevation'] for node in nodes.values() if node.get('elevation') is not None]
if elevations:
    min_elevation = min(elevations)
    max_elevation = max(elevations)

    # Handle log scaling safely
    offset = -min_elevation + 1 if min_elevation <= 0 else 0
    log_min = np.log(min_elevation + offset)
    log_max = np.log(max_elevation + offset)

    colormap = cm.LinearColormap(
        colors=['#4287f5', '#4a30db', 'orange', 'red'],
        index=[log_min, log_min + (log_max - log_min) * 0.3,
               log_min + (log_max - log_min) * 0.6, log_max],
        vmin=log_min, vmax=log_max
    )
    colormap.caption = 'Elevation (meters) - Logarithmic Scale'
    m.add_child(colormap)

    for way in ways:
        try:
            way_nodes_ids = way['nodes']
            for i in range(len(way_nodes_ids) - 1):
                node1 = nodes.get(way_nodes_ids[i])
                node2 = nodes.get(way_nodes_ids[i+1])

                if node1 and node2 and node1['elevation'] is not None and node2['elevation'] is not None:
                    avg_elevation = (node1['elevation'] + node2['elevation']) / 2
                    log_avg = np.log(avg_elevation + offset)
                    color = colormap(log_avg)

                    coords = [(node1['lat'], node1['lon']), (node2['lat'], node2['lon'])]
                    folium.PolyLine(coords, color=color, weight=5, opacity=0.8).add_to(m)

        except KeyError as e:
            print(f"Skipping segment in way {way['id']} due to missing node {e}")

# -------------------------
# Add QGIS Curves from CSV
# -------------------------
def parse_qgis_coords(coord_str):
    """
    Parse QGIS POINT strings like:
    [<QgsPointXY: POINT(8105863.0268 2149442.8568)>, ...]
    Assumes EPSG:3857 projection, converts to lat/lon.
    """
    # Extract all coordinate pairs using regex
    matches = re.findall(r"POINT\(([\d\.\-]+) ([\d\.\-]+)\)", coord_str)
    coords_latlon = []
    for x_str, y_str in matches:
        x, y = float(x_str), float(y_str)
        # Convert from Web Mercator (EPSG:3857) to lat/lon
        lon = (x / 6378137.0) * (180.0 / np.pi)
        lat = (y / 6378137.0) * (180.0 / np.pi)
        lat = (180.0 / np.pi) * (2 * np.arctan(np.exp(lat * np.pi / 180.0)) - np.pi / 2)
        coords_latlon.append((lat, lon))
    return coords_latlon

try:
    with open("curve-updated.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            coord_str = row["Coordinates"]
            curve_coords = parse_qgis_coords(coord_str)
            if len(curve_coords) > 1:
                arc_length = row.get('Arc Length (m)', 'N/A')
                angle = row.get('Angle (deg)', 'N/A')

                if arc_length != 'N/A':
                    arc_length = f"{float(arc_length):.2f}"  # 2 decimal places
                if angle != 'N/A':
                    angle = f"{float(angle):.2f}"

                tooltip_text = f"Arc Length: {arc_length} m\nangle: {angle}°"
                popup_text = f"<div style='font-size:14px;'><b>Arc Length:</b> {arc_length}m<br><b>Angle:</b> {angle}°</div>"

                folium.PolyLine(
                    locations=curve_coords,
                    color="black",
                    weight=1.3,
                    opacity=1,
                ).add_to(m)
                
                # Clickable hitbox (transparent)
                folium.PolyLine(
                    locations=curve_coords,
                    color="transparent",
                    weight=6,  # big invisible click zone
                    opacity=0.0,
                    tooltip=tooltip_text,
                    popup=popup_text
                ).add_to(m)


except FileNotFoundError:
    print("No qgis_curves.csv found. Skipping curve overlay.")

# -------------------------
# Save Map
# -------------------------
m.save('mumbai_railways_with_curves.html')
print("Map saved as mumbai_railways_with_curves.html")
