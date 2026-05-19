import streamlit as st
import numpy as np
import pandas as pd
import random
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from collections import defaultdict


# ------------------------------------------------------------
# 1. DATA INITIALIZATION (200 Cabs with realistic data)
# ------------------------------------------------------------
@st.cache_resource
def init_taxis():
    np.random.seed(42)
    taxi_ids = list(range(1, 201))

    # Realistic Bangalore locations with coordinates
    locations_data = {
        "MG Road": (12.9762, 77.6033, 850), "Indiranagar": (12.9784, 77.6408, 720),
        "Koramangala": (12.9279, 77.6271, 980), "Whitefield": (12.9698, 77.7499, 450),
        "Electronic City": (12.8453, 77.6603, 380), "Jayanagar": (12.9308, 77.5803, 650),
        "Yeshwanthpur": (13.0285, 77.5506, 420), "Hebbal": (13.0359, 77.597, 530),
        "Marathahalli": (12.9552, 77.7012, 610), "BTM Layout": (12.9169, 77.6109, 890),
        "HSR Layout": (12.9120, 77.6414, 750), "Church Street": (12.9745, 77.6062, 820),
        "Richmond Road": (12.9697, 77.6060, 790), "Lavelle Road": (12.9739, 77.6045, 810),
        "Residency Road": (12.9700, 77.6055, 830), "Brigade Road": (12.9752, 77.6068, 840),
        "Commercial Street": (12.9812, 77.6071, 780), "Ulsoor": (12.9826, 77.6245, 700),
        "Frazer Town": (12.9988, 77.6149, 680), "Kalyan Nagar": (13.0073, 77.6434, 590)
    }

    locations = list(locations_data.keys())
    taxi_locations = [random.choice(locations) for _ in range(200)]

    # More realistic status distribution
    statuses = np.random.choice(["Available", "On Trip", "Offline"], size=200, p=[0.45, 0.45, 0.10])

    # Driver details
    driver_names = [f"Driver_{i}" for i in range(1, 201)]
    car_models = np.random.choice(["Swift Dzire", "Etios", "Indigo", "Xcent", "Amaze", "Honda City", "i20", "Verna"],
                                  200)
    driver_ratings = np.random.uniform(3.5, 5.0, 200).round(1)
    total_trips = np.random.randint(50, 5000, 200)
    acceptance_rate = np.random.uniform(85, 99, 200).round(1)

    # Earnings data
    today_earnings = np.random.uniform(500, 5000, 200).round(2)

    return pd.DataFrame({
        "TaxiID": taxi_ids,
        "Driver": driver_names,
        "Car": car_models,
        "Location": taxi_locations,
        "Status": statuses,
        "Rating": driver_ratings,
        "Total Trips": total_trips,
        "Acceptance Rate": acceptance_rate,
        "Today's Earnings": today_earnings
    }), locations_data


# ------------------------------------------------------------
# 2. QUICK SORT by distance
# ------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c


def quick_sort_by_distance(taxis_list, pickup_location, locations_data):
    if len(taxis_list) <= 1:
        return taxis_list

    pickup_coords = locations_data.get(pickup_location, (12.9716, 77.5946, 0))[:2]

    def get_distance(taxi):
        taxi_coords = locations_data.get(taxi["Location"], (12.9716, 77.5946, 0))[:2]
        return haversine_distance(pickup_coords[0], pickup_coords[1], taxi_coords[0], taxi_coords[1])

    pivot = taxis_list[0]
    left = [t for t in taxis_list if get_distance(t) < get_distance(pivot)]
    middle = [t for t in taxis_list if get_distance(t) == get_distance(pivot)]
    right = [t for t in taxis_list if get_distance(t) > get_distance(pivot)]

    return quick_sort_by_distance(left, pickup_location, locations_data) + middle + quick_sort_by_distance(right,
                                                                                                           pickup_location,
                                                                                                           locations_data)


# ------------------------------------------------------------
# 3. LINEAR SEARCH
# ------------------------------------------------------------
def linear_search_available(taxis_df):
    available = []
    for idx, row in taxis_df.iterrows():
        if row["Status"] == "Available":
            available.append(row)
    return available


# ------------------------------------------------------------
# 4. ETA with traffic simulation
# ------------------------------------------------------------
def calculate_eta(distance_km):
    hour = datetime.now().hour
    if 8 <= hour <= 11 or 17 <= hour <= 20:
        traffic_factor = np.random.uniform(1.8, 2.5)
    elif 23 <= hour <= 5:
        traffic_factor = np.random.uniform(0.7, 1.0)
    else:
        traffic_factor = np.random.uniform(1.0, 1.5)

    avg_speed = 25 / traffic_factor
    eta_minutes = (distance_km / avg_speed) * 60
    return round(eta_minutes, 1), round(traffic_factor, 1)


# ------------------------------------------------------------
# 5. DEMAND HEATMAP DATA
# ------------------------------------------------------------
def generate_heatmap_data(request_log, locations_data):
    if len(request_log) == 0:
        # Return random heatmap data for demo
        heat_data = []
        for loc, (lat, lon, _) in locations_data.items():
            intensity = np.random.randint(10, 100)
            heat_data.append([lat, lon, intensity])
        return heat_data

    zone_demand = defaultdict(int)
    for req in request_log:
        zone_demand[req['pickup']] += 1

    heat_data = []
    for loc, (lat, lon, _) in locations_data.items():
        intensity = zone_demand.get(loc, 0)
        if intensity > 0:
            heat_data.append([lat, lon, intensity * 10])

    return heat_data


# ------------------------------------------------------------
# 6. ANALYTICS FUNCTIONS
# ------------------------------------------------------------
def get_fleet_metrics(taxis_df, request_log):
    available = len(taxis_df[taxis_df["Status"] == "Available"])
    ontrip = len(taxis_df[taxis_df["Status"] == "On Trip"])
    offline = len(taxis_df[taxis_df["Status"] == "Offline"])

    avg_rating = taxis_df["Rating"].mean()
    total_trips_today = taxis_df["Today's Earnings"].sum() / 200  # Approximate
    total_earnings = taxis_df["Today's Earnings"].sum()

    # Demand metrics
    total_requests = len(request_log)
    completed_trips = len([r for r in request_log if r.get('completed', False)])

    return {
        "available": available, "ontrip": ontrip, "offline": offline,
        "avg_rating": avg_rating, "total_trips": int(total_trips_today),
        "total_earnings": total_earnings, "total_requests": total_requests,
        "completion_rate": (completed_trips / total_requests * 100) if total_requests > 0 else 0
    }


def get_performance_metrics(taxis_df):
    # Top performers
    top_rated = taxis_df.nlargest(5, "Rating")[["Driver", "Rating", "Total Trips", "Acceptance Rate"]]
    top_earners = taxis_df.nlargest(5, "Today's Earnings")[["Driver", "Today's Earnings", "Total Trips"]]

    # Zone wise availability
    zone_stats = taxis_df[taxis_df["Status"] == "Available"]["Location"].value_counts().head(10)

    return top_rated, top_earners, zone_stats


# ------------------------------------------------------------
# 7. DISPATCH FUNCTION
# ------------------------------------------------------------
def dispatch_taxi(taxis_df, pickup, destination, locations_data):
    available = linear_search_available(taxis_df)

    if not available:
        return None, "No cabs available", None

    sorted_available = quick_sort_by_distance(available, pickup, locations_data)
    best_taxi = sorted_available[0]

    # Calculate distance
    pickup_coords = locations_data.get(pickup, (12.9716, 77.5946, 0))[:2]
    dest_coords = locations_data.get(destination, (12.9716, 77.5946, 0))[:2]
    distance = haversine_distance(pickup_coords[0], pickup_coords[1], dest_coords[0], dest_coords[1])

    eta, traffic = calculate_eta(distance)

    # Dynamic fare
    base_fare = 25
    if distance <= 1.5:
        fare = base_fare
    else:
        fare = base_fare + (distance - 1.5) * 15

    surge = 1.0
    if eta < 10:
        surge = 1.5
    elif eta < 15:
        surge = 1.3

    final_fare = round(fare * surge, 0)

    # Update taxi status
    taxis_df.loc[taxis_df["TaxiID"] == best_taxi["TaxiID"], "Status"] = "On Trip"

    return best_taxi, eta, {"distance": round(distance, 1), "fare": final_fare, "traffic": traffic, "surge": surge}


# ------------------------------------------------------------
# 8. STREAMLIT APP - COMPLETE DASHBOARD
# ------------------------------------------------------------
st.set_page_config(page_title="Taxi Dispatch System", page_icon="🚕", layout="wide")

# Custom CSS for modern dashboard
st.markdown("""
<style>
    /* Global styles */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #e9edf2 100%);
    }

    /* Metric cards */
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 1rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: transform 0.3s;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1a1a1a;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.5rem;
    }

    /* Dashboard cards */
    .dashboard-card {
        background: white;
        border-radius: 20px;
        padding: 1.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }

    /* Header */
    .dashboard-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 1.5rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        width: 100%;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102,126,234,0.4);
    }

    /* Dataframes */
    .dataframe {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Tags */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .status-available { background: #d4edda; color: #155724; }
    .status-ontrip { background: #fff3cd; color: #856404; }
    .status-offline { background: #f8d7da; color: #721c24; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "taxis" not in st.session_state:
    st.session_state.taxis, st.session_state.locations_data = init_taxis()
if "request_log" not in st.session_state:
    st.session_state.request_log = []
if "current_ride" not in st.session_state:
    st.session_state.current_ride = None
if "heatmap_data" not in st.session_state:
    st.session_state.heatmap_data = None

# Header
st.markdown("""
<div class="dashboard-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin: 0; font-size: 2rem;">🚕 Taxi Dispatch System</h1>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.8;">Real-time fleet management • 200 cabs • Smart dispatching</p>
        </div>
        <div>
            <p style="margin: 0;">⚡ Live Operations</p>
            <p style="margin: 0; font-size: 0.8rem;">{} Update</p>
        </div>
    </div>
</div>
""".format(datetime.now().strftime("%H:%M:%S")), unsafe_allow_html=True)

# Get metrics
metrics = get_fleet_metrics(st.session_state.taxis, st.session_state.request_log)

# Top row - Key Metrics
st.markdown("### 📊 Key Metrics")
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{metrics['available']}</div>
        <div class="metric-label">✅ Available Cabs</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{metrics['ontrip']}</div>
        <div class="metric-label">🚖 On Trip</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{metrics['offline']}</div>
        <div class="metric-label">⛔ Offline</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">⭐ {metrics['avg_rating']:.1f}</div>
        <div class="metric-label">Avg Driver Rating</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">₹{metrics['total_earnings']:,.0f}</div>
        <div class="metric-label">Today's Earnings</div>
    </div>
    """, unsafe_allow_html=True)

with col6:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{metrics['completion_rate']:.0f}%</div>
        <div class="metric-label">Completion Rate</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Row 2 - Analytics, Heatmap, and Fleet Management
tab1, tab2, tab3, tab4 = st.tabs(["📱 Book Ride", "🗺️ Heatmap & Demand", "📈 Analytics Dashboard", "🚕 Fleet Management"])

# TAB 1: Book Ride
with tab1:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown("### 📍 Book a Ride")

        pickup = st.selectbox("Pickup Location", list(st.session_state.locations_data.keys()), key="pickup")
        destination = st.selectbox("Destination", list(st.session_state.locations_data.keys()), key="dest")

        cola, colb = st.columns(2)
        with cola:
            ride_type = st.selectbox("Ride Type", ["Mini", "Sedan", "SUV"])
        with colb:
            payment = st.selectbox("Payment", ["Cash", "UPI", "Card"])

        if st.button("🔍 FIND CAB", use_container_width=True):
            with st.spinner("Finding nearest cab..."):
                best_taxi, eta, ride_details = dispatch_taxi(
                    st.session_state.taxis, pickup, destination, st.session_state.locations_data
                )

                if best_taxi is None:
                    st.error("❌ No cabs available. Please try again.")
                else:
                    st.session_state.current_ride = {
                        "taxi": best_taxi, "eta": eta, "pickup": pickup,
                        "destination": destination, "details": ride_details,
                        "time": datetime.now()
                    }
                    st.session_state.request_log.append({
                        "timestamp": datetime.now(), "pickup": pickup,
                        "destination": destination, "driver": best_taxi["Driver"],
                        "eta": eta, "fare": ride_details["fare"], "completed": False
                    })
                    st.success("✅ Cab assigned successfully!")
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        if st.session_state.current_ride:
            ride = st.session_state.current_ride
            st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
            st.markdown("### 🚖 Active Ride")

            st.info(f"""
            **Driver:** {ride['taxi']['Driver']} ⭐ {ride['taxi']['Rating']}

            **Car:** {ride['taxi']['Car']}

            **From:** {ride['pickup']}

            **To:** {ride['destination']}

            **ETA:** {ride['eta']} minutes
            """)

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 1rem; border-radius: 12px; text-align: center; color: white;">
                <span style="font-size: 0.9rem;">Fare</span><br>
                <span style="font-size: 2rem; font-weight: bold;">₹{ride['details']['fare']}</span>
                <span style="font-size: 0.8rem;"> (Surge {ride['details']['surge']}x)</span>
            </div>
            """, unsafe_allow_html=True)

            if st.button("✓ Complete Trip", use_container_width=True):
                # Mark ride as completed
                for req in st.session_state.request_log:
                    if req['driver'] == ride['taxi']['Driver'] and not req['completed']:
                        req['completed'] = True
                        req['completion_time'] = datetime.now()
                        break

                st.session_state.current_ride = None
                st.success("Trip completed! Thank you for riding with us.")
                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

# TAB 2: Heatmap & Demand Analysis
with tab2:
    st.markdown("### 🗺️ Real-time Demand Heatmap")

    # Generate heatmap data
    heat_data = generate_heatmap_data(st.session_state.request_log, st.session_state.locations_data)

    # Create map
    center_lat = 12.9716
    center_lon = 77.5946
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='CartoDB positron')

    # Add heatmap
    HeatMap(heat_data, radius=20, blur=15, max_zoom=13).add_to(m)

    # Add markers for locations
    for loc, (lat, lon, demand) in st.session_state.locations_data.items():
        # Calculate demand intensity
        ride_count = len([r for r in st.session_state.request_log if r['pickup'] == loc])
        if ride_count > 0:
            folium.CircleMarker(
                [lat, lon], radius=8, color='red', fill=True,
                popup=f"{loc}<br>Rides: {ride_count}", weight=2
            ).add_to(m)

    col1, col2 = st.columns([3, 1])
    with col1:
        st_folium(m, width=700, height=500)

    with col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown("### 📊 Demand Insights")

        # Calculate high demand zones
        zone_demand = {}
        for req in st.session_state.request_log:
            zone_demand[req['pickup']] = zone_demand.get(req['pickup'], 0) + 1

        if zone_demand:
            demand_counts = np.array(list(zone_demand.values()))
            if len(demand_counts) > 0:
                percentile_80 = np.percentile(demand_counts, 80)
                high_demand_zones = [zone for zone, count in zone_demand.items() if count >= percentile_80]

                st.markdown("#### 🔥 High Demand Zones")
                for zone in high_demand_zones[:5]:
                    st.markdown(f"• **{zone}** - {zone_demand[zone]} requests")

                st.markdown("#### 💡 Recommendations")
                st.info("""
                - Deploy 15-20 additional cabs to high-demand zones
                - Consider surge pricing (1.3x - 1.8x)
                - Reduce ETA by positioning cabs strategically
                """)
        else:
            st.info("No ride data yet. Book some rides to see demand patterns!")

        st.markdown('</div>', unsafe_allow_html=True)

# TAB 3: Analytics Dashboard
with tab3:
    st.markdown("### 📈 Performance Analytics")

    # Get performance data
    top_rated, top_earners, zone_stats = get_performance_metrics(st.session_state.taxis)

    # Row 1 - Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown("#### ⭐ Top Rated Drivers")
        st.dataframe(top_rated, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown("#### 💰 Top Earners Today")
        st.dataframe(top_earners, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Row 2 - Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown("#### 📊 Cabs by Location")
        fig = px.bar(x=zone_stats.values, y=zone_stats.index, orientation='h',
                     title="Available Cabs per Zone", color=zone_stats.values,
                     color_continuous_scale='Viridis')
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown("#### 🚦 Status Distribution")
        status_counts = st.session_state.taxis["Status"].value_counts()
        fig = px.pie(values=status_counts.values, names=status_counts.index,
                     title="Fleet Status Distribution", color_discrete_sequence=['#00b894', '#fdcb6e', '#e17055'])
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Trip history chart
    if st.session_state.request_log:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.markdown("#### 📅 Ride History")
        rides_df = pd.DataFrame(st.session_state.request_log[-20:])
        rides_df['hour'] = pd.to_datetime(rides_df['timestamp']).dt.hour
        hourly_rides = rides_df.groupby('hour').size()

        fig = px.line(x=hourly_rides.index, y=hourly_rides.values,
                      title="Rides by Hour", markers=True)
        fig.update_layout(xaxis_title="Hour of Day", yaxis_title="Number of Rides")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# TAB 4: Fleet Management
with tab4:
    st.markdown("### 🚕 Fleet Management Console")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.multiselect("Filter by Status", ["Available", "On Trip", "Offline"],
                                       default=["Available", "On Trip", "Offline"])
    with col2:
        rating_filter = st.slider("Min Rating", 3.5, 5.0, 3.5, 0.1)
    with col3:
        search_driver = st.text_input("Search Driver", placeholder="Driver name...")

    # Apply filters
    filtered_df = st.session_state.taxis[st.session_state.taxis["Status"].isin(status_filter)]
    filtered_df = filtered_df[filtered_df["Rating"] >= rating_filter]
    if search_driver:
        filtered_df = filtered_df[filtered_df["Driver"].str.contains(search_driver, case=False)]

    # Display fleet
    st.markdown(f"**Showing {len(filtered_df)} cabs**")


    # Add status badges
    def add_status_badge(status):
        badge_class = {
            "Available": "status-available",
            "On Trip": "status-ontrip",
            "Offline": "status-offline"
        }.get(status, "")
        return f'<span class="status-badge {badge_class}">{status}</span>'


    # Display dataframe with styling
    display_df = filtered_df.copy()
    display_df["Status"] = display_df["Status"].apply(add_status_badge)
    st.markdown(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)

    # Bulk actions
    st.markdown("---")
    st.markdown("### ⚙️ Fleet Actions")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Export Fleet Report", use_container_width=True):
            csv = st.session_state.taxis.to_csv(index=False)
            st.download_button("Download CSV", csv, "fleet_report.csv", "text/csv")

    with col2:
        if st.button("🔄 Refresh Fleet Status", use_container_width=True):
            st.rerun()

    with col3:
        if st.button("⚡ Optimize Dispatch Algorithm", use_container_width=True):
            st.info("Dispatch optimization complete! Using Quick Sort for nearest cab assignment.")

# Footer
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.caption("🚙 200 Active Drivers")
with col2:
    st.caption("⚡ Quick Sort + Linear Search")
with col3:
    st.caption("📊 Real-time Heatmap Analytics")
with col4:
    st.caption("⭐ 4.8 Average Rating")
