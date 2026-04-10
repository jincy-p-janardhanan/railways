import json
import folium
import branca.colormap as cm
import numpy as np
import re
import csv
from folium import Element

# -------------------------
# Load GeoJSON
# -------------------------
with open("mumbai_railways_updated_with_elevations.geojson", "r") as f:
    geojson_data = json.load(f)

nodes = {}
ways = []

node_counter = 1
for feature in geojson_data["features"]:
    coords = feature["geometry"]["coordinates"]

    way_nodes_ids = []
    for coord in coords:
        lon, lat, elevation = coord
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

# -------------------------
# Map setup
# -------------------------
all_lats = [n["lat"] for n in nodes.values()]
all_lons = [n["lon"] for n in nodes.values()]
center_lat = (min(all_lats) + max(all_lats)) / 2
center_lon = (min(all_lons) + max(all_lons)) / 2

m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles='cartodbpositron')

# -------------------------
# Elevation colormap
# -------------------------
elevations = [n['elevation'] for n in nodes.values() if n['elevation'] is not None]
elevations = np.array(elevations)

min_elevation = elevations.min()
max_elevation = elevations.max()

index = np.percentile(elevations, [0,30,75,85,90,92.5,93.5,94.4,95.5,96.35,97.5,98.7,100])
index = np.unique(index)
print(index)
colors = [
    "#eaf2f8","#9fd7fc","#76d7c4","#82e0aa","#f7dc6f","#f5b041",
    "#eb984e","#ec7063","#e74c3c","#ff6fb5","#ff4dd2","#ff66ff","#ff99ff"
][:len(index)]

colormap = cm.LinearColormap(colors=colors, index=index, vmin=min_elevation, vmax=max_elevation)
colormap.tick_labels = [f"{int(i)}" for i in index]
colormap.caption = 'Elevation (meters)'
m.add_child(colormap)

# -------------------------
# Store elevation segments (for JS)
# -------------------------
elevation_segments = []

for way in ways:
    for i in range(len(way['nodes']) - 1):
        n1 = nodes[way['nodes'][i]]
        n2 = nodes[way['nodes'][i+1]]

        if n1['elevation'] is not None and n2['elevation'] is not None:
            avg = (n1['elevation'] + n2['elevation']) / 2

            coords = [(n1['lat'], n1['lon']), (n2['lat'], n2['lon'])]

            elevation_segments.append({
                "coords": coords,
                "elevation": avg
            })

            # Draw ONLY visual line (no popup)
            folium.PolyLine(
                coords,
                color=colormap(avg),
                weight=5,
                opacity=0.85
            ).add_to(m)

# -------------------------
# Parse QGIS coords
# -------------------------
def parse_qgis_coords(coord_str):
    matches = re.findall(r"POINT\(([\d\.\-]+) ([\d\.\-]+)\)", coord_str)
    coords_latlon = []

    for x_str, y_str in matches:
        x, y = float(x_str), float(y_str)
        lon = (x / 6378137.0) * (180.0 / np.pi)
        lat = (y / 6378137.0) * (180.0 / np.pi)
        lat = (180.0 / np.pi) * (2 * np.arctan(np.exp(lat * np.pi / 180.0)) - np.pi / 2)
        coords_latlon.append((lat, lon))

    return coords_latlon

# -------------------------
# Add curves + JS click binding
# -------------------------
arc_data_list = []

try:
    with open("curve-updated.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            coords = parse_qgis_coords(row["Coordinates"])

            if len(coords) > 1:
                arc_length = float(row.get('Arc Length (m)', 0))
                radius = float(row.get('Radius (m)', 0))
                angle = float(row.get('Angle (deg)', 0))

                arc_data_list.append({
                    "coords": coords,
                    "arc_length": arc_length,
                    "radius": radius,
                    "angle": angle
                })

                # Draw arc
                folium.PolyLine(
                    locations=coords,
                    color="black",
                    weight=2,
                    opacity=1
                ).add_to(m)

except:
    print("Curve file missing")

js_code = f"""
setTimeout(function() {{

    var map = window.{m.get_name()};

    console.log("JS LOADED");

    var elevationData = {json.dumps(elevation_segments)};
    var arcData = {json.dumps(arc_data_list)};

    function dist(a,b,c,d){{
        return Math.sqrt((a-c)*(a-c)+(b-d)*(b-d));
    }}

    // -------------------------
    // Nearest Elevation
    // -------------------------
    function nearestElevation(lat, lon){{
        let minD = Infinity;
        let val = null;

        elevationData.forEach(seg => {{
            seg.coords.forEach(pt => {{
                let d = dist(lat, lon, pt[0], pt[1]);
                if(d < minD){{
                    minD = d;
                    val = seg.elevation;
                }}
            }});
        }});

        return {{
            elevation: val,
            distance: minD
        }};
    }}

    // -------------------------
    // Nearest Arc
    // -------------------------
    function nearestArc(lat, lon){{
        let minD = Infinity;
        let best = null;

        arcData.forEach(a => {{
            a.coords.forEach(pt => {{
                let d = dist(lat, lon, pt[0], pt[1]);
                if(d < minD){{
                    minD = d;
                    best = a;
                }}
            }});
        }});

        return {{
            arc: best,
            distance: minD
        }};
    }}

    // -------------------------
    // Click Handler
    // -------------------------
    map.on('click', function(e){{
        console.log("CLICK DETECTED");

        let lat = e.latlng.lat;
        let lon = e.latlng.lng;

        let arcResult = nearestArc(lat, lon);
        let elevResult = nearestElevation(lat, lon);

        let arc = arcResult.arc;
        let arcDist = arcResult.distance;

        let elev = elevResult.elevation;
        let elevDist = elevResult.distance;

        console.log("arcDist:", arcDist, "elevDist:", elevDist);

        // -------------------------
        // Tunable Parameters
        // -------------------------
        let ARC_THRESHOLD = 0.0025;      // ~100m
        let ELEV_THRESHOLD = 0.0015;    // ~150m
        

        // -------------------------
        // CASE 1: Arc dominates
        // -------------------------
        if (
            arc &&
            arcDist <= ARC_THRESHOLD 
        ) {{

            let html = `
                <div style="font-size:14px;">
                    <b>Arc Length:</b> ${{arc.arc_length.toFixed(2)}} m<br>
                    <b>Radius:</b> ${{arc.radius.toFixed(2)}} m<br>
                    <b>Angle:</b> ${{arc.angle.toFixed(2)}}°<br>
                    <b>Elevation:</b> ${{elev !== null ? elev.toFixed(2) : "N/A"}} m
                </div>
            `;

            L.popup()
                .setLatLng(e.latlng)
                .setContent(html)
                .openOn(map);

            return;
        }}

        // -------------------------
        // CASE 2: Elevation only
        // -------------------------
        if (elev && elevDist <= ELEV_THRESHOLD) {{

            let html = `
                <div style="font-size:14px;">
                    <b>Elevation:</b> ${{elev.toFixed(2)}} m
                </div>
            `;

            L.popup()
                .setLatLng(e.latlng)
                .setContent(html)
                .openOn(map);

            return;
        }}

        // -------------------------
        // CASE 3: Nothing nearby
        // -------------------------
        console.log("Nothing nearby");

    }});

}}, 800);
"""

m.get_root().script.add_child(Element(js_code))

# -------------------------
# Save
# -------------------------
m.save("mumbai_railways_with_curves.html")
print("Map saved.")
# verify on https://indiarailinfo.com/station/map/mumbai-csm-terminus-csmt/12282#st