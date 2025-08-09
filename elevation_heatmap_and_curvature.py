import json
import folium
import branca.colormap as cm
import numpy as np 

# Load GeoJSON
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

# 3. Create Elevation Heatmap on Folium Map
# -----------------------------------------
center_lat = (min_lat + max_lat) / 2
center_lon = (min_lon + max_lon) / 2
m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

# Create a colormap for elevation
elevations = [node['elevation'] for node in nodes.values() if node.get('elevation') is not None]
if elevations:
    min_elevation = min(elevations)
    max_elevation = max(elevations)

    # To handle log(0) or log(negative), we shift all values to be positive.
    # The offset ensures the minimum elevation value becomes 1.
    offset = -min_elevation + 1 if min_elevation <= 0 else 0

    # Calculate the log-transformed range for the colormap
    log_min = np.log(min_elevation + offset)
    log_max = np.log(max_elevation + offset)
    
    # Create a colormap that is linear on the log-transformed elevation data
    colormap = cm.LinearColormap(colors=['#4287f5', '#4a30db', 'orange', 'red'],
                                 index=[log_min, log_min + (log_max - log_min) * 0.3,
                                        log_min + (log_max - log_min) * 0.6, log_max],
                                 vmin=log_min, vmax=log_max)
    colormap.caption = 'Elevation (meters) - Logarithmic Scale'
    
    m.add_child(colormap)

    # Draw railway lines with heatmap colors
    for way in ways:
        try:
            way_nodes_ids = way['nodes']
            for i in range(len(way_nodes_ids) - 1):
                node1_id = way_nodes_ids[i]
                node2_id = way_nodes_ids[i+1]
                
                node1 = nodes.get(node1_id)
                node2 = nodes.get(node2_id)

                if node1 and node2 and node1.get('elevation') is not None and node2.get('elevation') is not None:
                    avg_elevation = (node1['elevation'] + node2['elevation']) / 2
                    log_avg_elevation = np.log(avg_elevation + offset)
                    color = colormap(log_avg_elevation)
                    
                    coords = [
                        (node1['lat'], node1['lon']),
                        (node2['lat'], node2['lon'])
                    ]
                    
                    folium.PolyLine(
                        locations=coords,
                        color=color,
                        weight=5,
                        opacity=0.8,
                        popup=f"Elevation: {avg_elevation:.2f}m"
                    ).add_to(m)

        except KeyError as e:
            print(f"Skipping segment in way {way['id']} due to missing node {e}")
            continue

    m.save('mumbai_railways_elevation_heatmap_log.html')
    print("\nElevation heatmap map saved as mumbai_railways_elevation_heatmap.html")

else:
    print("\nCould not generate heatmap as no elevation data was available.")