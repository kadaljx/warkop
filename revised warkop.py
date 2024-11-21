import geopandas as gpd
import pandas as pd
import random
import requests
import time
import math
from shapely.geometry import Point

# ---------------------------
# Step 1: Load and Inspect Shapefile
# ---------------------------

# Load the Surabaya shapefile
shapefile_path = "ADMINISTRASIDESA_AR_25K.shp"
surabaya = gpd.read_file(shapefile_path)

# Check the coordinate reference system (CRS)
print("Coordinate Reference System (CRS):")
print(surabaya.crs)

# Reproject to a projected CRS for accurate area calculations
if surabaya.crs is None or surabaya.crs.is_geographic:
    # UTM Zone 49S is suitable for East Java, Indonesia
    print("\nReprojecting to a projected coordinate system for accurate area calculations...")
    surabaya = surabaya.to_crs(epsg=32749)  # EPSG:32749 corresponds to UTM Zone 49S
else:
    print("\nCRS is already projected. No reprojection needed.")

# Calculate the area of each polygon (in square meters)
surabaya['area_sqm'] = surabaya['geometry'].area

# Calculate the total area of Surabaya (sum of all polygons)
total_area_sqm = surabaya['area_sqm'].sum()
total_area_sqkm = total_area_sqm / 1e6  # Convert square meters to square kilometers
total_area_sqkm = round(total_area_sqkm, 2)

print(f"\nTotal area of Surabaya: {total_area_sqkm} square kilometers")

# Reproject back to WGS84 (latitude and longitude) for sampling and API queries
surabaya = surabaya.to_crs(epsg=4326)

# ---------------------------
# Step 2: Stratified Sampling in a 10x10 Grid
# ---------------------------

def random_coordinate_in_cell(min_lat, max_lat, min_lon, max_lon):
    random_longitude = random.uniform(min_lon, max_lon)
    random_latitude = random.uniform(min_lat, max_lat)
    return random_latitude, random_longitude

# Grid dimensions
n, m = 10, 10  # n columns (longitude), m rows (latitude)
min_lon, min_lat, max_lon, max_lat = surabaya.total_bounds
delta_lon = (max_lon - min_lon) / n
delta_lat = (max_lat - min_lat) / m

sample_points = []

for i in range(n):
    for j in range(m):
        print(f"\nSampling from grid cell ({i+1}, {j+1})...")
        for k in range(5):  # 5 samples per cell
            print(f"Sample {k+1} of 5")
            latitude, longitude = random_coordinate_in_cell(
                min_lat + j * delta_lat,
                min_lat + (j + 1) * delta_lat,
                min_lon + i * delta_lon,
                min_lon + (i + 1) * delta_lon
            )
            point = Point(longitude, latitude)
            if surabaya.geometry.contains(point).any():
                sample_points.append({'Latitude': latitude, 'Longitude': longitude})
            else:
                continue  # Point is outside Surabaya

# ---------------------------
# Step 3: Google Places API Query
# ---------------------------

def get_nearby_warkop_places(latitude, longitude, api_key):
    endpoint_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    all_results = []
    params = {
        'location': f'{latitude},{longitude}',
        'radius': 350,  # 350 meters radius
        'keyword': 'warkop',
        'key': api_key,
    }

    response = requests.get(endpoint_url, params=params).json()
    all_results.extend(response.get('results', []))

    # Handle pagination if necessary
    while 'next_page_token' in response:
        next_page_token = response['next_page_token']
        time.sleep(2)  # Delay required for next_page_token to become valid
        params['pagetoken'] = next_page_token
        response = requests.get(endpoint_url, params=params).json()
        all_results.extend(response.get('results', []))

    return [{'name': result['name'], 'place_id': result['place_id'], 'geometry': result['geometry']} for result in all_results]

# ---------------------------
# Step 4: Collect Data from API
# ---------------------------

api_key = 'YOUR_GOOGLE_API_KEY'  # Replace with your actual API key
results_data = []

# Keep track of unique 'warkop' by place_id
unique_warkop = {}

for idx, sample in enumerate(sample_points):
    latitude = sample['Latitude']
    longitude = sample['Longitude']
    print(f"\nProcessing sample {idx+1}/{len(sample_points)} at location ({latitude}, {longitude})")

    results = get_nearby_warkop_places(latitude, longitude, api_key)

    if not results:
        # If no 'warkop' businesses are found
        unique_key = f"{latitude}_{longitude}_NoWarkop"
        if unique_key not in unique_warkop:
            unique_warkop[unique_key] = {
                'Sample Latitude': latitude,
                'Sample Longitude': longitude,
                'Business Name': 'No warkop',
                'Place ID': 'N/A',
                'Latitude': latitude,
                'Longitude': longitude,
                'Google Maps URL': 'N/A'
            }
    else:
        for place in results:
            place_id = place['place_id']
            if place_id not in unique_warkop:
                unique_warkop[place_id] = {
                    'Sample Latitude': latitude,
                    'Sample Longitude': longitude,
                    'Business Name': place['name'],
                    'Place ID': place_id,
                    'Latitude': place['geometry']['location']['lat'],
                    'Longitude': place['geometry']['location']['lng'],
                    'Google Maps URL': f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                }

# Convert unique 'warkop' to DataFrame
warkop_df = pd.DataFrame.from_dict(unique_warkop, orient='index')

# ---------------------------
# Step 5: Calculate Averages and Estimate Total 'Warkop'
# ---------------------------

# Number of unique 'warkop' found
total_unique_warkop = warkop_df[warkop_df['Business Name'] != 'No warkop'].shape[0]
print(f"\nTotal unique 'warkop' found: {total_unique_warkop}")

# Number of samples
number_of_samples = len(sample_points)
print(f"Number of samples: {number_of_samples}")

# Calculate average 'warkop' per sample
average_warkop_per_sample = total_unique_warkop / number_of_samples
print(f"Average 'warkop' per sample: {average_warkop_per_sample:.3f}")

# Area per sample (circle with radius 0.35 km)
area_per_sample = math.pi * (0.35 ** 2)  # Area in square kilometers
print(f"Area per sample (km^2): {area_per_sample:.5f}")

# Calculate 'warkop' density per square kilometer
warkop_density = average_warkop_per_sample / area_per_sample
print(f"'Warkop' density per km^2: {warkop_density:.2f}")

# Calculate estimated total number of 'warkop' in Surabaya
estimated_total_warkop = warkop_density * total_area_sqkm
estimated_total_warkop = round(estimated_total_warkop)
print(f"\nEstimated total number of 'warkop' in Surabaya: {estimated_total_warkop}")

# ---------------------------
# Step 6: Save Results to CSV
# ---------------------------

def export_to_csv(data):
    data.to_csv('warkop_results_10x10.csv', index=False, encoding='utf-8-sig')

# Export the warkop data to CSV
export_to_csv(warkop_df)

print("\nData has been saved to 'warkop_results_10x10.csv'.")
