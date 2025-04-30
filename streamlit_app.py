import streamlit as st
import requests
from geopy.distance import geodesic
import base64
import os
import json
from groq import Groq

# --- Page Config ---
st.set_page_config(page_title="Accident Assistant 🚑", page_icon="🚑", layout="wide")

# --- Constants ---
GROQ_API_KEY = "my_api_key"
HISTORY_FILE = "location_history.json"

# --- Custom CSS ---
st.markdown("""
    <style>
    html, body {
        font-family: 'Segoe UI', sans-serif;
        background: #f0f2f6;
    }
    .title {
        font-size: 3.2em;
        font-weight: 800;
        color: #0b5394;
        text-align: center;
        margin-top: 0.5em;
        margin-bottom: 0.2em;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    .subtitle {
        font-size: 1.4em;
        color: #555;
        text-align: center;
        margin-bottom: 2em;
    }
    .card {
        background-color: #ffffff;
        padding: 1.5em;
        margin: 1em 0;
        border-radius: 15px;
        box-shadow: 0 6px 16px rgba(0,0,0,0.08);
    }
    .contact-box {
        background-color: #e7f3ff;
        border-left: 6px solid #1c7ed6;
        padding: 1.2em;
        margin: 1.5em 0;
        border-radius: 10px;
        font-family: 'Segoe UI', sans-serif;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        color: #003366;
        font-size: 1.05em;
        white-space: pre-wrap;
    }
    .contact-box h3 {
        margin-top: 0;
        margin-bottom: 0.8em;
        color: #0b5394;
    }
    </style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

def get_nearby_places(lat, lon, place_type, radius=5000):
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["amenity"="{place_type}"](around:{radius},{lat},{lon});
      way["amenity"="{place_type}"](around:{radius},{lat},{lon});
      relation["amenity"="{place_type}"](around:{radius},{lat},{lon});
    );
    out center;
    """
    response = requests.get(overpass_url, params={'data': query})
    data = response.json()
    places = []
    for element in data['elements']:
        name = element['tags'].get('name', 'Unnamed')
        lat_place = element.get('lat') or element.get('center', {}).get('lat')
        lon_place = element.get('lon') or element.get('center', {}).get('lon')
        if lat_place and lon_place:
            distance = geodesic((lat, lon), (lat_place, lon_place)).meters
            places.append({'name': name, 'lat': lat_place, 'lon': lon_place, 'distance': distance})
    return min(places, key=lambda x: x['distance'], default=None)

def find_nearest_hospital_and_police(lat, lon):
    return get_nearby_places(lat, lon, "hospital"), get_nearby_places(lat, lon, "police")

def contact_info(hospital_name, police_name):
    client = Groq(api_key=GROQ_API_KEY)
    query = f"Can you provide the contact number and address of {hospital_name} and {police_name}?"
    try:
        res = client.chat.completions.create(
            messages=[{"role": "user", "content": query}],
            model="meta-llama/llama-4-scout-17b-16e-instruct",
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"❌ Error: {e}"

def describe_accident(base64_image):
    client = Groq(api_key=GROQ_API_KEY)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the accident scene in detail."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]
                }
            ],
            model="meta-llama/llama-4-scout-17b-16e-instruct",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"❌ Error describing accident scene: {e}"

def load_location_history():
    return json.load(open(HISTORY_FILE)) if os.path.exists(HISTORY_FILE) else []

def save_location_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

# --- Initialization ---
if "location_history" not in st.session_state:
    st.session_state.location_history = load_location_history()

# --- Header ---
st.markdown('<div class="title">🚑 Accident Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Get Immediate Help and Smart Scene Analysis</div>', unsafe_allow_html=True)

# --- File Upload Section ---
uploaded_image = st.file_uploader("📷 Upload Accident Scene Image", type=['jpg', 'jpeg', 'png'])

# --- Location Input Section (Moved Here) ---
if uploaded_image:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📍 Accident Location")

    prev_coords = [f"{lat},{lon}" for lat, lon in st.session_state.location_history]
    selected_coord = st.selectbox("📍 Previously Used Coordinates", ["Select"] + prev_coords, key="location_select")

    lat_col, lon_col = st.columns(2)
    if selected_coord != "Select":
        sel_lat, sel_lon = map(float, selected_coord.split(','))
        latitude = lat_col.number_input("Latitude", value=sel_lat, format="%.6f", key="lat_input")
        longitude = lon_col.number_input("Longitude", value=sel_lon, format="%.6f", key="lon_input")
    else:
        latitude = lat_col.number_input("Latitude", format="%.6f", key="lat_input")
        longitude = lon_col.number_input("Longitude", format="%.6f", key="lon_input")

    if [latitude, longitude] not in st.session_state.location_history:
        st.session_state.location_history.append([latitude, longitude])
        save_location_history(st.session_state.location_history)

    st.markdown('</div>', unsafe_allow_html=True)

# --- Buttons ---
analyze_col, sos_col = st.columns([1, 1])
with analyze_col:
    analyze_clicked = st.button("🔍 Analyze Accident")
with sos_col:
    sos_clicked = st.button("🚨 SOS Emergency Link")

# --- Analyze Logic ---
if analyze_clicked:
    if uploaded_image:
        base64_img = encode_image(uploaded_image)
        with st.spinner("Analyzing the accident scene..."):
            desc = describe_accident(base64_img)

        # Display Image and Description
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🖼 Accident Scene")
        img_col, desc_col = st.columns(2)
        with img_col:
            st.image(uploaded_image, caption="Uploaded Scene", use_container_width=True)
        with desc_col:
            st.markdown("#### Description")
            st.write(desc)
        st.markdown('</div>', unsafe_allow_html=True)

        # Find Hospital, Police and Contacts
        with st.spinner("Finding nearest hospital and police station..."):
            hospital, police = find_nearest_hospital_and_police(latitude, longitude)
            contact = contact_info(hospital['name'] if hospital else '', police['name'] if police else '')

        # Show Help Centers
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📍 Nearest Help")

        loc1, loc2 = st.columns(2)
        with loc1:
            st.markdown("### 🏥 Hospital")
            if hospital:
                st.write(f"*Name:* {hospital['name']}")
                st.write(f"*Location:* {hospital['lat']}, {hospital['lon']}")
                st.write(f"*Distance:* {hospital['distance']:.1f} meters")
            else:
                st.warning("No nearby hospital found.")

        with loc2:
            st.markdown("### 🚓 Police Station")
            if police:
                st.write(f"*Name:* {police['name']}")
                st.write(f"*Location:* {police['lat']}, {police['lon']}")
                st.write(f"*Distance:* {police['distance']:.1f} meters")
            else:
                st.warning("No nearby police station found.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Contact Info
        st.markdown(f"""
        <div class="contact-box">
            <h3>📞 Contact Information</h3>
            <pre>{contact}</pre>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("❌ Please upload an image to begin analysis.")

# --- SOS Button ---
if sos_clicked:
    sos_url = "https://sosjawaan.netlify.app/"
    st.markdown(
        f"""
        <a href="{sos_url}" target="_blank" style="
            background-color: #e63946;
            color: white;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            font-size: 18px;
            border-radius: 8px;
            font-weight: bold;
            display:inline-block;
            transition: 0.3s;
        ">
            🚨 Visit SOS Emergency Portal
        </a>
        """,
        unsafe_allow_html=True
    )

# --- Footer ---
st.markdown("---")
st.caption("Made with ❤ by Your Team | 2025")
