import requests
import folium
import json
import time
import branca.colormap as cm
import numpy as np 

# Selected region in Mumbai: https://bboxfinder.com/#18.881600,72.769318,19.358441,73.238297
# bounding_box = (18.881600, 72.769318, 19.358441, 73.238297)
bounding_box = (18.687879,72.463074,20.166833,73.847351)
min_lat, min_lon, max_lat, max_lon = bounding_box

# 1. Fetch Railway Data from OpenStreetMap
# -----------------------------------------
overpass_url = "http://overpass-api.de/api/interpreter"
query = f"""
[out:json][timeout:120];
(
  relation["railway"="rail"]["name"~"Central|Western|Harbour",i]({min_lat},{min_lon},{max_lat},{max_lon});
  way["railway"="rail"]["name"~"Central|Western|Harbour",i]({min_lat},{min_lon},{max_lat},{max_lon});
  
)->.lines; 
(
  way(r.lines);
  way.lines;
  
)->.all_ways; 
.all_ways out body; 
>;             
out skel qt;
"""

print("Fetching railway data from OpenStreetMap...")
response = requests.get(overpass_url, params={'data': query})
data = response.json()

nodes = {}
ways = []

for element in data['elements']:
    if element['type'] == 'node':
        nodes[element['id']] = {'lat': element['lat'], 'lon': element['lon']}
    elif element['type'] == 'way':
        ways.append(element)

print(f"Fetched {len(ways)} railway line segments")

with open("raw_osm_data.json", "w") as f:
    json.dump(data, f, indent=2)
print("Query result dumped as raw_osm_data.json")

# 2. Fetch Elevation Data
# -------------------------
def chunk_list(data, size):
    """Yield successive n-sized chunks from data."""
    for i in range(0, len(data), size):
        yield data[i:i + size]

locations = [(node_data['lat'], node_data['lon']) for node_data in nodes.values()]
elevation_results = []
batch_size = 100
i = 1

print("\nFetching elevation data for railway nodes...")
for batch in chunk_list(locations, batch_size):
    location_str = "|".join([f"{lat},{lon}" for lat, lon in batch])
    url = f"https://api.opentopodata.org/v1/srtm90m?locations={location_str}"
    try:
        r = requests.get(url)
        data = r.json()
        if "results" in data:
            elevation_results.extend(data["results"])
        else:
            print(f"API returned no results for a batch {i}")
        print(f"[Batch {i}] Status: {r.status_code}, Time: {r.elapsed.total_seconds():.2f}s")
    except Exception as e:
        print(f"Error fetching batch {i}: {e}")
    
    i += 1
    time.sleep(0.5)

# Add elevation data to our nodes
elevation_map = {
    (r['location']['lat'], r['location']['lng']): r.get('elevation')
    for r in elevation_results
}

for node_id, node_data in nodes.items():
    lat, lon = node_data['lat'], node_data['lon']
    if (lat, lon) in elevation_map:
        nodes[node_id]['elevation'] = elevation_map[(lat, lon)]
    else:
        nodes[node_id]['elevation'] = None 

print(f"\nFetched and processed elevations for {len(elevation_map)} points.")

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
    colormap = cm.LinearColormap(colors=['blue', 'green', 'yellow', 'red'],
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
    print("\nElevation heatmap map saved as mumbai_railways_elevation_heatmap1.html")

else:
    print("\nCould not generate heatmap as no elevation data was available.")


# 4. Export to GeoJSON
# --------------------
print("\nExporting data to GeoJSON...")
features = []
for way in ways:
    try:
        coordinates = []
        for node_id in way['nodes']:
            node = nodes.get(node_id)
            if node:
                # GeoJSON format is [longitude, latitude, elevation]
                coordinates.append([
                    node['lon'],
                    node['lat'],
                    node.get('elevation', 0) # Use 0 if elevation is not available
                ])
        
        feature = {
            "type": "Feature",
            "properties": {
                "name": way.get('tags', {}).get('name', 'Unnamed Railway'),
                "id": way['id']
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            }
        }
        features.append(feature)
    except KeyError as e:
        print(f"Skipping way {way['id']} in GeoJSON export due to missing node {e}")

feature_collection = {
    "type": "FeatureCollection",
    "features": features
}

with open("mumbai_railways.geojson", "w") as f:
    json.dump(feature_collection, f, indent=2)

print("Railway data exported to mumbai_railways.geojson")