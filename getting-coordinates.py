import requests
import folium
import random
import json
import time

# Selected region in Mumbai: https://bboxfinder.com/#18.881600,72.769318,19.358441,73.238297
bounding_box = (18.881600, 72.769318, 19.358441, 73.238297)
min_lat, min_lon, max_lat, max_lon = bounding_box

overpass_url = "http://overpass-api.de/api/interpreter"
query = f"""
[out:json][timeout:60];
(
  way["railway"="rail"]["name"~"Central|Western",i]({min_lat},{min_lon},{max_lat},{max_lon});
);
out body;
>;
out skel qt;
"""

response = requests.get(overpass_url, params={'data': query})
data = response.json()

nodes = {}
ways = []

for element in data['elements']:
    if element['type'] == 'node':
        nodes[element['id']] = (element['lat'], element['lon'])
    elif element['type'] == 'way':
        ways.append(element)

print(f"Fetched {len(ways)} railway line segments")

with open("raw_osm_data.json", "w") as f:
    json.dump(data, f, indent=2)
    
print("Query result dumped as raw_osm_data.json")

with open("railway_nodes.json", "w") as f:
    json.dump(nodes, f, indent=2)

print("Nodes extracted dumped as railway_nodes.json")

with open("railway_ways.json", "w") as f:
    json.dump(ways, f, indent=2)

print("Ways extracted dumped as railway_ways.json")


# To preview selected railway lines
center_lat = (min_lat + max_lat) / 2
center_lon = (min_lon + max_lon) / 2
m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

def random_color():
    return "#" + ''.join(random.choices("0123456789ABCDEF", k=6))

for way in ways:
    try:
        coords = [nodes[node_id] for node_id in way['nodes']]
        name = way.get('tags', {}).get('name', 'Unnamed')
        color = random_color()
        folium.PolyLine(locations=coords, color=color, weight=4, popup=name).add_to(m)
    except KeyError as e:
        print(f"Skipping way {way['id']} due to missing node {e}")
        continue

m.save('mumbai_railways.html')
print("Extracted railway map saved as mumbai_railways.html")

def chunk_list(data, size):
    """Yield successive n-sized chunks from data."""
    for i in range(0, len(data), size):
        yield data[i:i + size]

locations = [v for v in nodes.values()]

elevation_results = []
batch_size = 100
i = 1
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
        print(r.text)
    except Exception as e:
        print(f"Error: {e}")
    
    i+=1
    time.sleep(0.5)  # timeout

output = [
    {
        "latitude": r['location']['lat'],
        "longitude": r['location']['lng'],
        "altitude_m": r.get('elevation')
    }
    for r in elevation_results
]

with open("railway_points_with_elevation.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Fetched elevations for {len(output)} points.")

