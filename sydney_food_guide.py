import streamlit as st
import pandas as pd
import folium
from geopy.distance import geodesic
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import requests 
from streamlit_js_eval import streamlit_js_eval, get_geolocation

print("My name is actually jeff")

# Load the data
@st.cache_data
def load_data():
    return pd.read_csv(
        "Sydney Food Guide.csv",
        encoding='latin1'  
    )
df = load_data()

# App title
st.title("Sydney Food Finder")
st.write("Enter your location and distance to find food spots near you!")

location = streamlit_js_eval(js_expressions=get_geolocation(), key="get_location")

if location and location.get("coords"):
    st.success("✅ Got user location")
else:
    st.warning("⚠️ Location unavailable — using default")

# Wait until location is received
if "user_location" not in st.session_state:
    if location is None:
        st.info("📍 Waiting for location access...")
        st.stop()
    elif location.get("coords"):
        user_lat = location["coords"]["latitude"]
        user_lon = location["coords"]["longitude"]
        st.session_state.user_location = (user_lat, user_lon)
        st.session_state.map_center = (user_lat, user_lon)
        st.success(f"✅ Using your location: {user_lat:.5f}, {user_lon:.5f}")
        st.rerun()
    else:
        st.session_state.user_location = (-33.87172, 151.2067)  # QVB
        st.session_state.map_center = st.session_state.user_location
        st.info("⚠️ Using default location (QVB). Location access was denied or failed.")
        st.rerun()

user_location = st.session_state.user_location

if "map_center" not in st.session_state:
    st.session_state.map_center = st.session_state.user_location  # fallback to user location

# User inputs 
radius = st.number_input("Enter search radius (in meters):", value=500, step=100)
address = st.text_input("📍 Enter a location or place name:")
geolocator = Nominatim(user_agent="food-finder", timeout=5)

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
    selected_categories= st.multiselect("Select cuisines:", all_categories, default=[])  # or empty by default

# Price filter
all_prices = sorted(df["Price"].dropna().unique())
selected_all = st.checkbox("All Prices", value=True)

if selected_all:
    selected_prices = all_prices
else:
    selected_prices = st.multiselect("Select prices:", all_prices, default=all_prices[:2])  # or empty by default

# Suburb filter
all_suburbs = sorted(df["Suburb"].dropna().unique())
selected_all = st.checkbox("All Suburbs", value=True)

if selected_all: 
    selected_suburbs = all_suburbs
else: 
    selected_suburbs = st.multiselect("Select suburbs:", all_suburbs, default=[])  # or empty by default

st.markdown("### 🗺️ Map")

# Recenter button in top-right-like position using columns
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("Recenter", use_container_width=True):
        st.session_state.map_center = st.session_state.user_location
        if st.session_state.get("selected_place") != None:
            del st.session_state.selected_place
        st.rerun()
        
# Create the map
m = folium.Map(location=st.session_state.map_center, zoom_start=14, titles="CartoDB Positron")
folium.Marker(
    location=st.session_state.user_location,
    popup="You are here",
    icon=folium.Icon(color="red")
).add_to(m)

for _, row in df.iterrows():
    if row["nearby"] and row["Category"] in selected_categories and row["Price"] in selected_prices and row["Suburb"] in selected_suburbs:
        color = "green"
    else:
        color = "blue"
    if row["Name"] == st.session_state.get("selected_place"):
        color = "purple"  # Highlight selected place
    popup_html = f"<b>{row['Name']}</b><br>Cuisine: {row['Category']}<br>Price: {row['Price']}"
    folium.Marker(
        location=(row["Y"], row["X"]),
        popup=folium.Popup(popup_html, max_width=250),
        icon=folium.Icon(color=color)
    ).add_to(m)

# Display the map in Streamlit
st_folium(m, width=725, height=500)

st.markdown("---")
st.subheader("📋 Explore Places by Cuisine")

for cuisine in sorted(df["Category"].dropna().unique()):
    with st.expander(f"{cuisine} ({(df['Category'] == cuisine).sum()} places)"):
        # Filter and sort
        cuisine_places = df[df["Category"] == cuisine].sort_values("Name")
        for _, row in cuisine_places.iterrows():
            button_label = f"{row['Name']}"
            if st.button(button_label, key=f"{row['Name']}-{row['X']}-{row['Y']}"):
                if st.session_state.get("selected_place") == row['Name']:
                    st.session_state.map_center = st.session_state.user_location
                    del st.session_state["selected_place"]
                else:
                    st.session_state.map_center = (row["Y"], row["X"])
                    st.session_state.selected_place = row['Name']
                st.rerun() # force an immediate re-render

            # Display extra info under each button
            st.markdown(
                f"<span style='color:blue'>Price:</span> {row['Price']}, "
                f"<span style='color:blue'>Suburb:</span> {row['Suburb']}",
                unsafe_allow_html=True
            )