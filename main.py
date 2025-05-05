import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from sklearn.cluster import DBSCAN

st.title('DSDE visualization')

DATA_PATH= './data/full_col.csv'

@st.cache_data
def load_data(nrows=None):
    data = pd.read_csv(DATA_PATH, nrows=nrows)
    data[['lon', 'lat']] = data['coords'].str.split(',', expand=True).astype(float) # convert lon lat to latitude and longitude
    return data

# Load data
data = load_data(5000)

## FILTER BY DATE
data['timestamp'] = pd.to_datetime(data['timestamp'])
min_date = data['timestamp'].min().date()
max_date = data['timestamp'].max().date()

start_date, end_date = st.sidebar.date_input(
    "Filter by Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)
start_dt = pd.to_datetime(start_date).tz_localize('UTC')
end_dt = pd.to_datetime(end_date).tz_localize('UTC') + pd.Timedelta(days=1)  # Include full day

data = data[(data['timestamp'] >= start_dt) & (data['timestamp'] < end_dt)]
# =============================

## COLOR STATE
state_select = st.sidebar.selectbox(
    'Select State to Filter',
    options=['ทั้งหมด','เสร็จสิ้น', 'กำลังดำเนินการ', 'รอรับเรื่อง'],
    index=0
)

if(state_select != 'ทั้งหมด'):
    data = data[data['state'] == state_select]

data['state'] = data['state'].apply(lambda x: x if x else "Unknown")
state_unique = data['state'].unique()
color_map = {
    "เสร็จสิ้น": [0, 255, 0],
    "กำลังดำเนินการ": [0, 0, 255],
    "รอรับเรื่อง": [255, 0, 0],
    "Unknown": [0, 0, 0]
}
data['color'] = data['state'].apply(lambda state: color_map.get(state, [0, 0, 0]))

# =============================

## SELECT BY TYPE ==========
import ast
def parse_set_string(s):
    try:
        parsed = ast.literal_eval(s)
        return list(parsed) if isinstance(parsed, set) else []
    except:
        return []

data['type_list'] = data['type'].apply(lambda x: parse_set_string(x) if pd.notnull(x) else [])
data['organization_list'] = data['organization'].apply(lambda x: ast.literal_eval(x) if pd.notnull(x) else [])

type_list = ['ทั้งหมด', 'ความสะอาด', 'ร้องเรียน' ,'น้ำท่วม' ,'สะพาน' ,'ถนน' ,'ท่อระบายน้ำ' ,'ทางเท้า','จราจร', 'แสงสว่าง' ,'กีดขวาง' ,'เสียงรบกวน' ,'สายไฟ' ,'คลอง' ,'ความปลอดภัย','สัตว์จรจัด' ,'ต้นไม้' ,'การเดินทาง' ,'เสนอแนะ' ,'คนจรจัด']
type_select = st.sidebar.selectbox(
    'Select type to Filter',
    options=type_list,
    index=0
)

if(type_select != 'ทั้งหมด'):
    data = data[data['type_list'].apply(lambda x: type_select in x)]
## ===================================


## SELECT BY DISTRICT ==========
district = data['district'].unique().tolist()
district.pop(0);
district.insert(0, 'ทั้งหมด')
district_select = st.sidebar.selectbox(
    'Select District to Filter',
    options=district,
    index=0
)
if(district_select != 'ทั้งหมด'):
    data = data[data['district'] == district_select]

# Add map style selection in sidebar
st.sidebar.header('Map Settings')
map_style = st.sidebar.selectbox(
    'Select Base Map Style',
    options=['Dark', 'Light', 'Road', 'Satellite'],
    index=0
)

# Define map style dictionary
MAP_STYLES = {
    'Dark': 'mapbox://styles/mapbox/dark-v10',
    'Light': 'mapbox://styles/mapbox/light-v10',
    'Road': 'mapbox://styles/mapbox/streets-v11',
    'Satellite': 'mapbox://styles/mapbox/satellite-v9'
}

if st.checkbox('Show raw data'):
    st.subheader('Raw data')
    st.write(data)


# Display Histogram of ticket counts by type
st.subheader('Ticket Counts by Type')

type_list_chart = ['ความสะอาด', 'ร้องเรียน' ,'น้ำท่วม' ,'สะพาน' ,'ถนน' ,'ท่อระบายน้ำ' ,'ทางเท้า','จราจร', 'แสงสว่าง' ,'กีดขวาง' ,'เสียงรบกวน' ,'สายไฟ' ,'คลอง' ,'ความปลอดภัย','สัตว์จรจัด' ,'ต้นไม้' ,'การเดินทาง' ,'เสนอแนะ' ,'คนจรจัด']
count = [0] * len(type_list_chart)
for type_list in data['type_list']:
    for t in type_list:
        if t in type_list_chart:
            count[type_list_chart.index(t)] += 1

chart = pd.DataFrame({
    'Type': type_list_chart,
    'Count': count  
    }
)

st.bar_chart(chart.set_index('Type'))


# Map visualization options
map_type = st.radio('Select Map Type', ['Points', 'Heatmap', 'Cluster'])

# Calculate map center
center_lat = data['lat'].mean()
center_lon = data['lon'].mean()




# Create map layers based on selection
def create_map_layers(data, map_type):
    if map_type == 'Points':
        return [
            pdk.Layer(
                "ScatterplotLayer",
                data,
                get_position="[lon, lat]",
                get_color='color',
                get_radius=50,
                opacity=0.8,
                pickable=True
            )
        ]
    elif map_type == 'Heatmap':
        return [
            pdk.Layer(
                "HeatmapLayer",
                data,
                get_position="[lon, lat]",
                opacity=0.8,
                radiusPixels=50,
            )
        ]
    elif map_type == 'Cluster':
        # Clustering using DBSCAN
        coords_rad = np.radians(data[['lat', 'lon']].values)

        # Apply DBSCAN with haversine metric
        kms_per_radian = 6371.0088  # Earth's radius
        eps_km = .3  # set this to the distance you consider as "close" (e.g., 2 km)

        eps_km = st.slider(
            'Select Distance (km)',
            min_value=0.1,
            max_value=1.0,
            value=0.3,
        )
        min_samples = st.slider(
            'Select Minimum Samples',
            min_value=1,
            max_value=10,
            value=2,
        )
        cluster = DBSCAN(
            eps=eps_km / kms_per_radian,  # epsilon in radians
            min_samples=min_samples,
            algorithm='ball_tree',
            metric='haversine'
        ).fit_predict(coords_rad)

        data['cluster'] = cluster

        label_colors = {}
        for label in np.unique(cluster):
            if label == -1:
                # Noise is gray
                label_colors[label] = (160, 160, 160)
            else:
                # Random bright color
                label_colors[label] = tuple(np.random.randint(50, 255) for _ in range(3))
        data['cluster_color'] = data['cluster'].map(label_colors)
        return [
            pdk.Layer(
                "ScatterplotLayer",
                data,
                get_position="[lon, lat]",
                get_color='cluster_color',
                get_radius=50,
                opacity=0.8,
                pickable=True
            )
        ]

tooltip = {
    "html": """
        <b>📄 Ticket ID:</b> {ticket_id} <br/>
        <b>💬 Comment:</b> {comment} <br/>
        <b>🖼️ Before:</b><br/>
        <img src="{photo}" width="100"/> <br/>
        <b>🧾 Type:</b> {type_list} <br/>
        <b>📌 State:</b> {state} <br/>
    """,
    "style": {
        "backgroundColor": "white",
        "color": "black",
        "width": "400px",
        "height": "auto",
        "fontSize": "12px",
    }
}

# Create and display the map
deck = pdk.Deck(
    layers=create_map_layers(data, map_type),
    initial_view_state=pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=11,
        pitch=0,
    ),
    map_style=MAP_STYLES[map_style],
    tooltip=tooltip,
)


st.pydeck_chart(deck)

df_time = data.copy()
df_time['date'] = df_time['timestamp'].dt.date
counts = df_time.groupby(['date', 'state']).size().unstack(fill_value=0)

st.line_chart(counts)





