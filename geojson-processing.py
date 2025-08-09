import json
import requests
import time

# ---------- CONFIG ----------
BATCH_SIZE = 100
ELEVATION_API = "https://api.opentopodata.org/v1/srtm90m"
INPUT_FILE = "mumbai_railways_updated.geojson"
OUTPUT_FILE = "mumbai_railways_updated_with_elevations.geojson"
# ----------------------------

# Helper to chunk locations
def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# Load GeoJSON
with open(INPUT_FILE, "r") as f:
    geojson_data = json.load(f)

locations_to_fetch = []  # (lat, lon, feature_index, coord_index)

# Step 1: Find missing elevations for id 1–99
for feature_idx, feature in enumerate(geojson_data["features"]):
    feature_id = feature["properties"].get("id", None)
    coords = feature["geometry"]["coordinates"]

    if feature_id is not None and 1 <= feature_id <= 99:
        for coord_idx, coord in enumerate(coords):
            lon, lat, *rest = coord
            elevation = rest[0] if rest else None

            if elevation is None:
                locations_to_fetch.append((lat, lon, feature_idx, coord_idx))

print(f"Total points needing elevation fetch: {len(locations_to_fetch)}")

# Step 2: Fetch missing elevations
if locations_to_fetch:
    print("\nFetching elevation data...")
    i = 1
    for batch in chunk_list(locations_to_fetch, BATCH_SIZE):
        location_str = "|".join([f"{lat},{lon}" for lat, lon, _, _ in batch])
        url = f"{ELEVATION_API}?locations={location_str}"
        try:
            r = requests.get(url)
            data = r.json()
            if "results" in data:
                for res, (_, _, feature_idx, coord_idx) in zip(data["results"], batch):
                    elev = res.get("elevation", None)
                    if elev is not None:
                        lon, lat = geojson_data["features"][feature_idx]["geometry"]["coordinates"][coord_idx][:2]
                        # Replace or add elevation in the coordinate triple
                        geojson_data["features"][feature_idx]["geometry"]["coordinates"][coord_idx] = [lon, lat, elev]
                print(f"[Batch {i}] Status: {r.status_code}, Time: {r.elapsed.total_seconds():.2f}s")
            else:
                print(f"[Batch {i}] API returned no results.")
        except Exception as e:
            print(f"[Batch {i}] Error: {e}")

        i += 1
        time.sleep(0.5)  # Avoid rate-limiting

# Step 3: Save updated GeoJSON
with open(OUTPUT_FILE, "w") as f:
    json.dump(geojson_data, f, indent=2)

print(f"\nUpdated GeoJSON saved as {OUTPUT_FILE}")