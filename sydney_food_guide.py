import streamlit as st
import pandas as pd
import folium
from geopy.distance import geodesic
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import requests 
from streamlit_js_eval import streamlit_js_eval, get_geolocation

# Load the data
@st.cache_data
def load_data():
    return pd.read_csv("Sydney Food Guide.csv")

df = load_data()

# App title
st.title("Sydney Food Finder")
st.write("Enter your location and distance to find food spots near you!")

# Default location: QVB
# user_lat = -33.87172
# user_lon = 151.2067

# Get user's location
location = streamlit_js_eval(js_expressions=get_geolocation(), key="get_location")

if location and location.get("coords"):
    user_lat = location["coords"]["latitude"]
    user_lon = location["coords"]["longitude"]
    st.success(f"Using your current location: {user_lat:.5f}, {user_lon:.5f}")
else:
    user_lat = -33.87172  # fallback (QVB)
    user_lon = 151.2067
    st.info("Using default location (QVB). Allow location access to use your real position.")

# User inputs 
radius = st.number_input("Enter search radius (in meters):", value=500, step=50)
address = st.text_input("📍 Enter a location or place name:")
geolocator = Nominatim(user_agent="food-finder", timeout=5)

# if address:
#     location = geolocator.geocode(address)

#     if location:
#         user_lat, user_lon = location.latitude, location.longitude
#         st.success(f"Found: {location.address}")
#     else:
#         st.error("Place not found. Try a more specific name or full address.")

if address:
    search_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 5,
        "addressdetails": 1,
        "viewbox": "150.6980,-34.0545,151.3092,-33.5957",  # Using min/max coordinates
        "bounded": 1  # restrict results to within viewbox
    }
    headers = {
        "User-Agent": "food-finder-app (your_email@example.com)"
    }

    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=10)

        # Ensure content is not empty before parsing
        if response.content:
            results = response.json()

            if results:
                options = [r["display_name"] for r in results]
                selected = st.selectbox("Choose a location:", options)

                selected_result = next(r for r in results if r["display_name"] == selected)
                user_lat = float(selected_result["lat"])
                user_lon = float(selected_result["lon"])
                user_location = (user_lat, user_lon)
                st.success(f"Selected location: {selected}")
            else:
                st.warning("No results found.")
        else:
            st.error("No response from Nominatim (empty content).")

    except Exception as e:
        st.error(f"Error searching address: {e}")

user_location = (user_lat, user_lon)

# Calculate distance and highlight nearby places
def is_nearby(row):
    place = (row["Y"], row["X"])
    return geodesic(user_location, place).meters <= radius

df["nearby"] = df.apply(is_nearby, axis=1)

# Category filter
all_categories = sorted(df["Category"].dropna().unique())
selected_all = st.checkbox("All Cuisines", value=True) 

if selected_all:
    selected_categories = all_categories
else:
    selected_categories= st.multiselect("Select cuisines:", all_categories, default=all_categories[:3])  # or empty by default

# Create the map
m = folium.Map(location=user_location, zoom_start=14, titles="CartoDB Positron")
folium.Marker(
    location=user_location,
    popup="You are here",
    icon=folium.Icon(color="red")
).add_to(m)

for _, row in df.iterrows():
    if row["nearby"] and row["Category"] in selected_categories:
        color = "green"
    else:
        color = "blue"
    popup_html = f"<b>{row['Name']}</b><br>Cuisine: {row['Category']}"
    folium.Marker(
        location=(row["Y"], row["X"]),
        popup=folium.Popup(popup_html, max_width=250),
        icon=folium.Icon(color=color)
    ).add_to(m)

# Display the map in Streamlit
st_folium(m, width=725, height=500)
